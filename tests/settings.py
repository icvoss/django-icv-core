"""
Minimal Django settings for icv-core tests.

Override ICV_CORE_* settings in individual test modules using pytest-django's
``settings`` fixture.
"""

SECRET_KEY = "icv-core-test-secret-key-not-for-production"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "icv_core",
    "core_testapp",
]

# Add DRF if available (audit API tests use importorskip)
try:
    import rest_framework  # noqa: F401

    INSTALLED_APPS.append("rest_framework")
except ImportError:
    pass

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"

# Use --no-migrations so pytest-django runs syncdb and picks up test models
# declared with app_label = "core_testapp".
MIGRATION_MODULES: dict = {
    "icv_core": None,
    "core_testapp": None,
    "auth": None,
    "contenttypes": None,
}

# ICV Core defaults — override per test with settings fixture
ICV_CORE_AUDIT_ENABLED = False
ICV_CORE_ALLOW_HARD_DELETE = False
ICV_CORE_TRACK_CREATED_BY = False


# ADR-101 decision 3: the logging-handler boot check (icv_core.E006) is an
# Error, so every settings module that runs system checks (makemigrations,
# migrate, check) must route the package logger to a handler. Propagation
# stays on so caplog and the root logger still see the records, and the root
# handler covers any sibling ICV package installed alongside this one.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {
        "icv_core": {"handlers": ["null"], "level": "WARNING", "propagate": True},
    },
    "root": {"handlers": ["null"]},
}
