from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CompanyOwnedModel(TimestampedModel):
    company = models.ForeignKey("companies.Company", on_delete=models.PROTECT)

    class Meta:
        abstract = True
