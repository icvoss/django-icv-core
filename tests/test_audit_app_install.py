"""Regression tests for issue #14.

``icv_core.audit`` in ``INSTALLED_APPS`` used to break ``django.setup()``
with a circular import between ``icv_core.models`` and ``icv_core.audit.models``.

These tests run Django setup and ``migrate`` in a subprocess because
``django.apps.apps.populate()`` only runs once per process: pytest-django
has already populated the app registry for the main test session using
``tests/settings.py``, so a second, differently-configured ``django.setup()``
call in-process would be a no-op and could not reproduce (or verify the fix
for) the import-order bug.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"

# Mirrors the documented install (README.md): "icv_core" in INSTALLED_APPS,
# ICV_CORE_AUDIT_ENABLED=True. This has always worked and must keep working.
DOCUMENTED_INSTALL_SCRIPT = """
import django
from django.conf import settings

settings.configure(
    INSTALLED_APPS=[
        "django.contrib.contenttypes",
        "django.contrib.auth",
        "icv_core",
    ],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    USE_TZ=True,
    ICV_CORE_AUDIT_ENABLED=True,
)
django.setup()

from icv_core.audit.models import AdminActivityLog, AuditEntry, SystemAlert  # noqa: E402

from django.core.management import call_command  # noqa: E402

call_command("migrate", verbosity=0)

assert AuditEntry._meta.app_label == "icv_core"
print("DOCUMENTED_INSTALL_OK")
"""

# Mirrors issue #14's repro: icv_core.audit added directly to INSTALLED_APPS.
AUDIT_SUBAPP_INSTALL_SCRIPT = """
import django
from django.conf import settings

settings.configure(
    INSTALLED_APPS=[
        "django.contrib.contenttypes",
        "django.contrib.auth",
        "icv_core.audit",
    ],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    USE_TZ=True,
)
django.setup()

from django.core.management import call_command  # noqa: E402

call_command("migrate", verbosity=0)

print("AUDIT_SUBAPP_INSTALL_OK")
"""


def _run_script(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=str(SRC_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_documented_install_still_works():
    """The README-documented install ("icv_core" only) must keep working."""
    result = _run_script(DOCUMENTED_INSTALL_SCRIPT)

    assert result.returncode == 0, result.stderr
    assert "DOCUMENTED_INSTALL_OK" in result.stdout


def test_icv_core_audit_in_installed_apps_does_not_raise_circular_import():
    """Regression test for #14.

    Adding "icv_core.audit" to INSTALLED_APPS must not raise ImportError
    from a circular import between icv_core.models and icv_core.audit.models,
    and `migrate` must complete.
    """
    result = _run_script(AUDIT_SUBAPP_INSTALL_SCRIPT)

    assert "ImportError" not in result.stderr, result.stderr
    assert "circular import" not in result.stderr, result.stderr
    assert result.returncode == 0, result.stderr
    assert "AUDIT_SUBAPP_INSTALL_OK" in result.stdout
