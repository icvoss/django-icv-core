"""Tests for icv-core settings/conf module."""

import importlib


class TestGetSetting:
    """get_setting() returns values from Django settings with fallback defaults."""

    def test_returns_default_when_setting_absent(self):
        from icv_core.conf import get_setting

        result = get_setting("NONEXISTENT_KEY_XYZ", "my_default")
        assert result == "my_default"

    def test_returns_override_from_django_settings(self, settings):
        settings.ICV_CORE_TEST_KEY = "overridden"
        from icv_core.conf import get_setting

        result = get_setting("TEST_KEY", "fallback")
        assert result == "overridden"

    def test_returns_none_when_no_default_given(self):
        from icv_core.conf import get_setting

        result = get_setting("ANOTHER_NONEXISTENT_KEY_ABC")
        assert result is None


class TestDefaultSettings:
    """Module-level settings have correct defaults."""

    def test_uuid_version_default(self):
        from icv_core import conf

        assert conf.ICV_CORE_UUID_VERSION == 4

    def test_allow_hard_delete_default(self):
        from icv_core import conf

        assert conf.ICV_CORE_ALLOW_HARD_DELETE is False

    def test_audit_enabled_default(self):
        from icv_core import conf

        assert conf.ICV_CORE_AUDIT_ENABLED is False

    def test_audit_retention_days_default(self):
        from icv_core import conf

        assert conf.ICV_CORE_AUDIT_RETENTION_DAYS == 365

    def test_track_created_by_default(self):
        from icv_core import conf

        assert conf.ICV_CORE_TRACK_CREATED_BY is False


class TestIcvAuthUserModel:
    """ICV_AUTH_USER_MODEL (ADR-037) falls back to settings.AUTH_USER_MODEL.

    conf.py resolves this as an eager module-level constant, the pattern
    every other setting in this module already uses, so ``override_settings``
    has no effect on an already-imported value: the module must be reloaded
    for a changed override to take effect, exactly like every other
    constant here (see TestDefaultSettings above). Each test reloads the
    module back to its pre-override state before returning, so a later test
    never sees a stale reloaded module left over from this one (the
    ``settings`` fixture reverts the underlying Django setting on teardown,
    but has no way to know ``conf`` needs reloading too).
    """

    def test_falls_back_to_auth_user_model_when_unset(self, settings):
        from icv_core import conf

        importlib.reload(conf)
        assert conf.ICV_AUTH_USER_MODEL == settings.AUTH_USER_MODEL == "auth.User"

    def test_honours_explicit_override(self, settings):
        settings.ICV_AUTH_USER_MODEL = "auth.Group"
        from icv_core import conf

        importlib.reload(conf)
        try:
            assert conf.ICV_AUTH_USER_MODEL == "auth.Group"
        finally:
            del settings.ICV_AUTH_USER_MODEL
            importlib.reload(conf)
