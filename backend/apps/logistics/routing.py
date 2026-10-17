import json
import math
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.request import urlopen

from django.conf import settings
from django.utils import timezone


def _great_circle_km(first, second):
    lat1, lon1 = map(math.radians, first)
    lat2, lon2 = map(math.radians, second)
    lat_delta = lat2 - lat1
    lon_delta = lon2 - lon1
    value = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(lon_delta / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(math.sqrt(value))


def great_circle_km(first, second):
    return _great_circle_km(first, second)


def _fallback_matrices(coordinates, speed_kph):
    distances = []
    durations = []
    for first in coordinates:
        distance_row = []
        duration_row = []
        for second in coordinates:
            distance = _great_circle_km(first, second)
            distance_row.append(distance)
            duration_row.append(distance / speed_kph * 3600)
        distances.append(distance_row)
        durations.append(duration_row)
    return distances, durations


def _valid_matrix(matrix, size):
    return (
        isinstance(matrix, list)
        and len(matrix) == size
        and all(
            isinstance(row, list)
            and len(row) == size
            and all(isinstance(value, (int, float)) and value >= 0 for value in row)
            for row in matrix
        )
    )


def route_matrices(coordinates, *, speed_kph):
    if not coordinates:
        return [], [], "fallback"
    if len(coordinates) == 1:
        return [[0.0]], [[0.0]], "fallback"

    if settings.ROUTING_EXTERNAL_ENABLED and settings.OSRM_BASE_URL:
        coordinate_path = ";".join(
            f"{longitude},{latitude}" for latitude, longitude in coordinates
        )
        url = (
            f"{settings.OSRM_BASE_URL.rstrip('/')}/table/v1/driving/"
            f"{coordinate_path}?annotations=distance,duration"
        )
        try:
            with urlopen(url, timeout=settings.ROUTING_TIMEOUT_SECONDS) as response:
                result = json.loads(response.read().decode("utf-8"))
            distances = result.get("distances")
            durations = result.get("durations")
            if _valid_matrix(distances, len(coordinates)) and _valid_matrix(
                durations, len(coordinates)
            ):
                return distances, durations, "osrm"
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, TypeError, ValueError):
            pass

    distances, durations = _fallback_matrices(coordinates, speed_kph)
    return distances, durations, "fallback"


def nearest_neighbor_order(matrix):
    if not matrix:
        return []
    if len(matrix) == 1:
        return [0]

    remaining = set(range(len(matrix)))
    first = min(
        remaining,
        key=lambda index: (
            sum(matrix[index][other] for other in remaining if other != index),
            index,
        ),
    )
    order = [first]
    remaining.remove(first)
    while remaining:
        current = order[-1]
        next_stop = min(remaining, key=lambda index: (matrix[current][index], index))
        order.append(next_stop)
        remaining.remove(next_stop)
    return order


def calculate_trip_route(trip):
    stops = list(trip.stops.select_related("shop").order_by("sequence", "pk"))
    if not stops:
        trip.routing_source = trip.RoutingSource.FALLBACK
        trip.save(update_fields=("routing_source", "updated_at"))
        return "fallback"

    coordinates = [
        (float(stop.shop.latitude), float(stop.shop.longitude)) for stop in stops
    ]
    distances, durations, source = route_matrices(
        coordinates, speed_kph=trip.company.average_route_speed_kph
    )
    order = nearest_neighbor_order(distances)
    now = timezone.make_aware(
        datetime.combine(trip.date, settings.ROUTE_START_TIME),
        timezone.get_current_timezone(),
    )
    window = timedelta(minutes=settings.ETA_WINDOW_MINUTES)
    stop_time = timedelta(minutes=trip.company.stop_duration_minutes)
    for sequence, stop_index in enumerate(order, start=1):
        if sequence > 1:
            previous_index = order[sequence - 2]
            now += timedelta(seconds=durations[previous_index][stop_index])
        stop = stops[stop_index]
        stop.sequence = sequence
        stop.eta = now
        stop.eta_window_from = now - window
        stop.eta_window_to = now + window
        stop.save(
            update_fields=(
                "sequence", "eta", "eta_window_from", "eta_window_to", "updated_at"
            )
        )
        now += stop_time

    trip.routing_source = source
    trip.save(update_fields=("routing_source", "updated_at"))
    return source
