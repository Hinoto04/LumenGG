from django.conf import settings
from django.db import models


class CatalogRelease(models.Model):
    version = models.CharField(max_length=64, unique=True)
    schema_version = models.PositiveIntegerField(default=1)
    min_client_version = models.CharField(max_length=20, default='1.0.0')
    source_hash = models.CharField(max_length=64)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField()
    filename = models.CharField(max_length=160)
    published_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

    class Meta:
        ordering = ['-id']


class SyncReceipt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    operation_id = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'operation_id'], name='mobile_sync_receipt_unique')]


class CalculatorReceipt(models.Model):
    session = models.ForeignKey('battlelog.BattleSession', on_delete=models.CASCADE)
    action_id = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['session', 'action_id'], name='mobile_calc_receipt_unique')]
