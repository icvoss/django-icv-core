"""
Tests for the icv-core audit concrete models' user FK target (ADR-037).

AuditEntry.user, AdminActivityLog.admin_user and SystemAlert.resolved_by
all target the resolved ICV_AUTH_USER_MODEL rather than
settings.AUTH_USER_MODEL directly, so a consumer that sets
ICV_AUTH_USER_MODEL differently from AUTH_USER_MODEL gets the override
honoured. With the override unset, the FK deconstructs identically to
settings.AUTH_USER_MODEL (proven by makemigrations --check against the
shipped migration, not by this file); these tests cover the field target
and the swappable machinery only.
"""

from django.apps import apps
from django.db import models

from icv_core.audit.models import AdminActivityLog, AuditEntry, SystemAlert
from icv_core.conf import ICV_AUTH_USER_MODEL


class TestAuditEntryUserField:
    def test_user_field_is_foreign_key(self):
        field = AuditEntry._meta.get_field("user")
        assert isinstance(field, models.ForeignKey)

    def test_user_field_targets_resolved_auth_user_model(self):
        field = AuditEntry._meta.get_field("user")
        assert field.remote_field.model._meta.label == ICV_AUTH_USER_MODEL

    def test_user_field_swappable_setting_is_auth_user_model(self):
        """The field's swappable_setting names AUTH_USER_MODEL, which is
        what makes Django deconstruct it via SettingsReference and keep
        shipped migrations byte-stable (ADR-037, "Migration-state
        consequence")."""
        field = AuditEntry._meta.get_field("user")
        assert field.swappable_setting == "AUTH_USER_MODEL"


class TestAdminActivityLogUserField:
    def test_admin_user_field_targets_resolved_auth_user_model(self):
        field = AdminActivityLog._meta.get_field("admin_user")
        assert field.remote_field.model._meta.label == ICV_AUTH_USER_MODEL

    def test_admin_user_field_swappable_setting_is_auth_user_model(self):
        field = AdminActivityLog._meta.get_field("admin_user")
        assert field.swappable_setting == "AUTH_USER_MODEL"


class TestSystemAlertResolvedByField:
    def test_resolved_by_field_targets_resolved_auth_user_model(self):
        field = SystemAlert._meta.get_field("resolved_by")
        assert field.remote_field.model._meta.label == ICV_AUTH_USER_MODEL

    def test_resolved_by_field_swappable_setting_is_auth_user_model(self):
        field = SystemAlert._meta.get_field("resolved_by")
        assert field.swappable_setting == "AUTH_USER_MODEL"


class TestIcvAuthUserModelResolvesToAnInstalledModel:
    """ICV_AUTH_USER_MODEL, as resolved in conf.py, names a real model.

    Guards against the resolved value drifting out of sync with whatever
    the test settings module actually installs.
    """

    def test_resolves_via_apps_get_model(self):
        app_label, model_name = ICV_AUTH_USER_MODEL.split(".")
        assert apps.get_model(app_label, model_name) is not None
