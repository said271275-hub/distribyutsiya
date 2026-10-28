import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Max
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.core.admin_api import company_for_request
from apps.core.permissions import CompanyAdminPermission
from apps.logistics.models import Trip, TripStop
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.payments.models import BalanceEntry, ShopBalance


REPORTS = {"sales", "debtors", "drivers", "products"}
MAX_REPORT_DAYS = 366
ISSUE_REASONS = {
    "shop_closed": "Do‘kon yopiq",
    "refused": "Do‘kon qabul qilmadi",
    "partial_delivery": "Qisman yetkazildi",
    "other": "Boshqa sabab",
}


class AdminReportResponseSerializer(serializers.Serializer):
    report = serializers.ChoiceField(choices=sorted(REPORTS))
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    summary = serializers.JSONField()
    rows = serializers.ListField(child=serializers.JSONField(), required=False)
    debtors = serializers.ListField(child=serializers.JSONField(), required=False)
    prepaid = serializers.ListField(child=serializers.JSONField(), required=False)


def _date_range(request):
    try:
        start_value = request.query_params["start_date"]
        end_value = request.query_params["end_date"]
        start_date = date.fromisoformat(start_value)
        end_date = date.fromisoformat(end_value)
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError(
            {"date": "start_date va end_date YYYY-MM-DD formatida majburiy."}
        ) from error
    if start_date.isoformat() != start_value or end_date.isoformat() != end_value:
        raise ValidationError(
            {"date": "start_date va end_date YYYY-MM-DD formatida majburiy."}
        )
    if start_date > end_date:
        raise ValidationError({"date": "Boshlanish sanasi tugash sanasidan keyin bo‘lmasin."})
    if (end_date - start_date).days + 1 > MAX_REPORT_DAYS:
        raise ValidationError({"date": "Sana oralig‘i 366 kundan oshmasligi kerak."})

    start = timezone.make_aware(datetime.combine(start_date, time.min))
    end = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
    return start_date, end_date, start, end


def _issues(company, start, end):
    return list(
        AuditLog.objects.filter(
            company=company,
            action="trip.stop.issue",
            entity_type="TripStop",
            created_at__gte=start,
            created_at__lt=end,
        ).values("entity_id", "after", "created_at")
    )


def _sales_report(company, start_date, end_date, start, end):
    delivered_events = OrderStatusHistory.objects.filter(
        order__company=company,
        status=Order.Status.DELIVERED,
        created_at__gte=start,
        created_at__lt=end,
    ).values("order_id", "created_at")
    delivered_orders_by_day = {}
    delivery_day_by_order = {}
    for event in delivered_events:
        event_date = timezone.localtime(event["created_at"]).date()
        delivered_orders_by_day.setdefault(event_date, set()).add(event["order_id"])
        delivery_day_by_order[event["order_id"]] = event_date
    delivered_amount_by_day = {}
    for item in OrderItem.objects.filter(
        company=company,
        order_id__in=delivery_day_by_order,
    ).values("order_id", "delivered_quantity", "quantity", "unit_price"):
        delivered_quantity = item["delivered_quantity"]
        amount = (
            (
                delivered_quantity
                if delivered_quantity is not None
                else item["quantity"]
            )
            * item["unit_price"]
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        event_date = delivery_day_by_order[item["order_id"]]
        delivered_amount_by_day[event_date] = (
            delivered_amount_by_day.get(event_date, Decimal("0.00")) + amount
        )
    cancelled_orders = {}
    for event in OrderStatusHistory.objects.filter(
        order__company=company,
        status=Order.Status.CANCELLED,
        created_at__gte=start,
        created_at__lt=end,
    ).values("order_id", "created_at"):
        event_date = timezone.localtime(event["created_at"]).date()
        cancelled_orders.setdefault(event_date, set()).add(event["order_id"])
    cancelled_by_day = {
        event_date: len(order_ids)
        for event_date, order_ids in cancelled_orders.items()
    }
    issue_orders_by_day = {}
    issue_records = _issues(company, start, end)
    for issue in issue_records:
        event_date = timezone.localtime(issue["created_at"]).date()
        issue_orders_by_day.setdefault(event_date, set()).update(
            (issue["after"] or {}).get("order_ids", [])
        )

    rows = []
    current_day = start_date
    while current_day <= end_date:
        delivered_orders = delivered_orders_by_day.get(current_day, set())
        rows.append(
            {
                "date": current_day.isoformat(),
                "delivered_orders": len(delivered_orders),
                "delivered_amount": str(
                    delivered_amount_by_day.get(current_day, Decimal("0.00"))
                ),
                "cancelled_orders": cancelled_by_day.get(current_day, 0),
                "problem_orders": len(issue_orders_by_day.get(current_day, set())),
            }
        )
        current_day += timedelta(days=1)

    return {
        "summary": {
            "delivered_orders": sum(row["delivered_orders"] for row in rows),
            "delivered_amount": str(
                sum((Decimal(row["delivered_amount"]) for row in rows), Decimal("0.00"))
            ),
            "cancelled_orders": sum(row["cancelled_orders"] for row in rows),
            "problem_orders": len(
                set().union(*issue_orders_by_day.values()) if issue_orders_by_day else set()
            ),
        },
        "rows": rows,
    }


def _debtors_report(company):
    balances = list(
        ShopBalance.objects.filter(
            company=company,
            shop__company_links__company=company,
            shop__company_links__is_active=True,
            shop__company_links__company__is_active=True,
        )
        .select_related("shop")
        .distinct()
    )
    latest_payment = {
        row["shop_id"]: row["last_payment_at"]
        for row in BalanceEntry.objects.filter(
            company=company,
            posted_at__isnull=False,
            payment__isnull=False,
            shop_id__in=[balance.shop_id for balance in balances],
        )
        .annotate(payment_date=Coalesce("payment__paid_at", "payment__created_at"))
        .values("shop_id")
        .annotate(last_payment_at=Max("payment_date"))
    }

    rows = [
        {
            "shop_id": balance.shop_id,
            "shop_name": balance.shop.name,
            "current_balance": str(balance.current_balance),
            "last_payment_date": (
                timezone.localtime(latest_payment[balance.shop_id]).date().isoformat()
                if balance.shop_id in latest_payment
                else None
            ),
        }
        for balance in balances
    ]
    debtors = sorted(
        (row for row in rows if Decimal(row["current_balance"]) > 0),
        key=lambda row: Decimal(row["current_balance"]),
        reverse=True,
    )
    prepaid = sorted(
        (row for row in rows if Decimal(row["current_balance"]) < 0),
        key=lambda row: Decimal(row["current_balance"]),
    )
    return {
        "summary": {
            "debtor_shops": len(debtors),
            "debt_total": str(
                sum(
                    (Decimal(row["current_balance"]) for row in debtors),
                    Decimal("0.00"),
                )
            ),
            "prepaid_shops": len(prepaid),
            "prepaid_total": str(
                sum(
                    (-Decimal(row["current_balance"]) for row in prepaid),
                    Decimal("0.00"),
                )
            ),
        },
        "debtors": debtors,
        "prepaid": prepaid,
    }


def _drivers_report(company, start_date, end_date, start, end):
    trips = list(
        Trip.objects.filter(
            company=company,
            date__range=(start_date, end_date),
        )
        .values("driver_id", "driver__user__phone")
        .annotate(trip_count=Count("pk", distinct=True))
        .order_by("driver__user__phone")
    )
    driver_rows = {
        row["driver_id"]: {
            "driver_id": row["driver_id"],
            "driver_phone": row["driver__user__phone"],
            "trips": row["trip_count"],
            "delivered_shops": set(),
            "problem_shops": set(),
            "reasons": {reason: 0 for reason in ISSUE_REASONS},
        }
        for row in trips
    }

    delivered_stops = (
        OrderStatusHistory.objects.filter(
            order__company=company,
            status=Order.Status.DELIVERED,
            created_at__gte=start,
            created_at__lt=end,
        )
        .values_list(
            "order__shop_id",
            "order__trip_stop_links__trip_stop__trip__driver_id",
        )
        .distinct()
    )
    for shop_id, driver_id in delivered_stops:
        if driver_id in driver_rows:
            driver_rows[driver_id]["delivered_shops"].add(shop_id)

    issues = _issues(company, start, end)
    stop_ids = {
        int(issue["entity_id"])
        for issue in issues
        if str(issue["entity_id"]).isdigit()
    }
    stop_drivers = dict(
        TripStop.objects.filter(company=company, pk__in=stop_ids).values_list(
            "pk", "trip__driver_id"
        )
    )
    for issue in issues:
        try:
            driver_id = stop_drivers.get(int(issue["entity_id"]))
        except (TypeError, ValueError):
            continue
        if driver_id not in driver_rows:
            continue
        row = driver_rows[driver_id]
        row["problem_shops"].add(issue["entity_id"])
        reason = (issue["after"] or {}).get("reason")
        if reason in row["reasons"]:
            row["reasons"][reason] += 1

    rows = [
        {
            **row,
            "delivered_shops": len(row["delivered_shops"]),
            "problem_shops": len(row["problem_shops"]),
        }
        for row in driver_rows.values()
    ]
    for row in rows:
        row["reasons"] = {
            reason: {
                "label": ISSUE_REASONS[reason],
                "count": row["reasons"][reason],
            }
            for reason in ISSUE_REASONS
        }
    return {
        "summary": {
            "trips": sum(row["trips"] for row in rows),
            "delivered_shops": sum(row["delivered_shops"] for row in rows),
            "problem_shops": sum(row["problem_shops"] for row in rows),
        },
        "rows": rows,
    }


def _products_report(company, start, end):
    delivered_orders = OrderStatusHistory.objects.filter(
        order__company=company,
        status=Order.Status.DELIVERED,
        created_at__gte=start,
        created_at__lt=end,
    ).values("order_id")
    product_totals = {}
    for item in OrderItem.objects.filter(
        order_id__in=delivered_orders,
        company=company,
    ).values(
        "product_id",
        "product__name",
        "product__unit",
        "delivered_quantity",
        "quantity",
        "unit_price",
    ):
        row = product_totals.setdefault(
            item["product_id"],
            {
                "product_id": item["product_id"],
                "product__name": item["product__name"],
                "product__unit": item["product__unit"],
                "delivered_quantity": Decimal("0.00"),
                "delivered_amount": Decimal("0.00"),
            },
        )
        quantity = (
            item["delivered_quantity"]
            if item["delivered_quantity"] is not None
            else item["quantity"]
        )
        row["delivered_quantity"] += quantity
        row["delivered_amount"] += (quantity * item["unit_price"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    rows = sorted(
        product_totals.values(),
        key=lambda row: (-row["delivered_quantity"], row["product__name"]),
    )
    return {
        "summary": {
            "products": len(rows),
            "delivered_amount": str(
                sum((row["delivered_amount"] or Decimal("0.00") for row in rows), Decimal("0.00"))
            ),
        },
        "rows": [
            {
                "product_id": row["product_id"],
                "product_name": row["product__name"],
                "unit": row["product__unit"],
                "delivered_quantity": str(row["delivered_quantity"] or Decimal("0.00")),
                "delivered_amount": str(row["delivered_amount"] or Decimal("0.00")),
            }
            for row in rows
        ],
    }


def _csv_response(report, report_name, start_date, end_date):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="{report_name}_{start_date}_{end_date}.csv"'
    )
    response.write("\ufeff")
    writer = csv.writer(response)

    def safe_text(value):
        text = str(value or "")
        if text.startswith(("=", "+", "-", "@", "\t", "\r")):
            return f"'{text}"
        return text

    if report_name == "sales":
        writer.writerow(
            ["Sana", "Yetkazilgan buyurtmalar", "Yetkazilgan summa", "Bekor qilingan", "Muammoli buyurtmalar"]
        )
        for row in report["rows"]:
            writer.writerow(
                [
                    row["date"],
                    row["delivered_orders"],
                    row["delivered_amount"],
                    row["cancelled_orders"],
                    row["problem_orders"],
                ]
            )
    elif report_name == "debtors":
        writer.writerow(["Holat", "Do‘kon", "Joriy qarz", "Oxirgi to‘lov sanasi"])
        for category, rows in (("Qarzdor", report["debtors"]), ("Oldindan to‘langan", report["prepaid"])):
            for row in rows:
                writer.writerow(
                    [
                        category,
                        safe_text(row["shop_name"]),
                        row["current_balance"],
                        row["last_payment_date"] or "",
                    ]
                )
    elif report_name == "drivers":
        writer.writerow(
            ["Haydovchi telefoni", "Reyslar", "Yetkazilgan do‘konlar", "Muammoli do‘konlar"]
            + [ISSUE_REASONS[reason] for reason in ISSUE_REASONS]
        )
        for row in report["rows"]:
            writer.writerow(
                [
                    safe_text(row["driver_phone"]),
                    row["trips"],
                    row["delivered_shops"],
                    row["problem_shops"],
                ]
                + [row["reasons"][reason]["count"] for reason in ISSUE_REASONS]
            )
    else:
        writer.writerow(["Mahsulot", "Birlik", "Yetkazilgan miqdor", "Yetkazilgan summa"])
        for row in report["rows"]:
            writer.writerow(
                [
                    safe_text(row["product_name"]),
                    row["unit"],
                    row["delivered_quantity"],
                    row["delivered_amount"],
                ]
            )
    return response


class AdminReportsView(APIView):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)

    @extend_schema(responses=AdminReportResponseSerializer)
    def get(self, request):
        report_name = request.query_params.get("report", "")
        if report_name not in REPORTS:
            raise ValidationError({"report": "Hisobot turini tanlang."})
        start_date, end_date, start, end = _date_range(request)
        company = company_for_request(request)

        if report_name == "sales":
            report = _sales_report(company, start_date, end_date, start, end)
        elif report_name == "debtors":
            report = _debtors_report(company)
        elif report_name == "drivers":
            report = _drivers_report(company, start_date, end_date, start, end)
        else:
            report = _products_report(company, start, end)

        if request.query_params.get("export") == "csv":
            return _csv_response(report, report_name, start_date, end_date)
        return Response(
            {
                "report": report_name,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                **report,
            }
        )
