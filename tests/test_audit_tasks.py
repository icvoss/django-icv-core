"""
Tests for icv_core.audit.tasks (ADR-037 second amendment, ruling 1).

log_event_async resolves the user model via apps.get_model(ICV_AUTH_USER_MODEL)
at call time, never django.contrib.auth.get_user_model(), so it agrees with
the user FKs (AuditEntry.user etc.) once a consumer sets ICV_AUTH_USER_MODEL
to a model other than AUTH_USER_MODEL.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from icv_core.audit.models import AuditEntry
from icv_core.audit.tasks import log_event_async

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="taskuser", password="pass")


@pytest.mark.django_db
class TestLogEventAsyncUserResolution:
    def test_resolves_user_via_apps_get_model(self, user):
        """Driving test: patch django.apps.apps.get_model (log_event_async
        imports apps inside the function body, so the patch target is the
        real django.apps.apps singleton, not a module-level name in
        icv_core.audit.tasks) and assert log_event_async calls it with the
        resolved ICV_AUTH_USER_MODEL, not get_user_model()."""
        with patch("django.apps.apps.get_model") as mock_get_model:
            mock_get_model.return_value = User
            log_event_async(
                event_type=AuditEntry.EventType.DATA,
                action=AuditEntry.Action.CREATE,
                user_id=str(user.pk),
                description="test",
                metadata={},
            )

        mock_get_model.assert_called_once_with("auth.User")

    def test_creates_audit_entry_with_resolved_user(self, user):
        """End-to-end: the created AuditEntry.user is the looked-up user,
        proving apps.get_model resolution actually wires through."""
        log_event_async(
            event_type=AuditEntry.EventType.DATA,
            action=AuditEntry.Action.CREATE,
            user_id=str(user.pk),
            description="test",
            metadata={},
        )

        entry = AuditEntry.objects.get(description="test")
        assert entry.user == user

    def test_none_user_id_skips_lookup(self):
        """No user_id: no model lookup at all, AuditEntry.user stays null."""
        with patch("django.apps.apps.get_model") as mock_get_model:
            log_event_async(
                event_type=AuditEntry.EventType.DATA,
                action=AuditEntry.Action.CREATE,
                user_id=None,
                description="no user",
                metadata={},
            )

        mock_get_model.assert_not_called()

    def test_does_not_call_get_user_model(self, user):
        """ADR-037 ruling 1: get_user_model() must never be called here,
        since it always returns the host's AUTH_USER_MODEL regardless of
        an ICV_AUTH_USER_MODEL override."""
        with patch("django.contrib.auth.get_user_model") as mock_get_user_model:
            log_event_async(
                event_type=AuditEntry.EventType.DATA,
                action=AuditEntry.Action.CREATE,
                user_id=str(user.pk),
                description="test 2",
                metadata={},
            )

        mock_get_user_model.assert_not_called()
