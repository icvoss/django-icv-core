"""
Celery tasks for the icv-core audit subsystem.

These tasks are only meaningful when ICV_CORE_AUDIT_ENABLED=True and Celery
is configured in the consuming project.
"""

from __future__ import annotations


def log_event_async(
    event_type: str,
    action: str,
    user_id: str | None,
    description: str,
    metadata: dict,
) -> None:
    """
    Write an AuditEntry from the Celery task wrapper when Celery is available.

    Called by icv_core.audit.services.log_event when async_mode=True.
    This function is wrapped as a Celery task at import time when Celery is
    available. Without Celery it remains an ordinary synchronous callable;
    callers invoking ``async_mode=True`` still require Celery because they
    call its ``.delay()`` method.

    A ``user_id`` that no longer resolves creates an entry with ``user=None``.
    This preserves the existing task contract, which treats a missing actor as
    an anonymous system event rather than refusing the audit write.
    """
    from icv_core.audit.models import AuditEntry

    user = None
    if user_id is not None:
        from django.apps import apps

        from icv_core.conf import ICV_AUTH_USER_MODEL

        User = apps.get_model(ICV_AUTH_USER_MODEL)
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            pass

    AuditEntry.objects.create(
        event_type=event_type,
        action=action,
        user=user,
        description=description,
        metadata=metadata,
    )


def archive_old_entries() -> int:
    """
    Archive AuditEntry rows older than ICV_CORE_AUDIT_RETENTION_DAYS.

    Returns the number of entries processed.

    Note: This implementation logs a message and returns 0 until the archive
    storage backend is configured. Consuming projects should override the
    archive target via settings.
    """
    import logging
    from datetime import timedelta

    from django.utils import timezone

    from icv_core.audit.models import AuditEntry
    from icv_core.conf import ICV_CORE_AUDIT_RETENTION_DAYS

    logger = logging.getLogger(__name__)
    cutoff = timezone.now() - timedelta(days=ICV_CORE_AUDIT_RETENTION_DAYS)
    old_entries = AuditEntry.objects.filter(created_at__lt=cutoff)
    count = old_entries.count()

    # Placeholder: consuming projects implement their own archive backend.
    logger.info("icv_core.audit: %d entries eligible for archival (cutoff: %s).", count, cutoff)
    return count


# Wrap as Celery tasks if Celery is available
try:
    from celery import shared_task  # type: ignore[import]

    log_event_async = shared_task(log_event_async)  # type: ignore[assignment]
    archive_old_entries = shared_task(archive_old_entries)  # type: ignore[assignment]
except ImportError:
    pass
