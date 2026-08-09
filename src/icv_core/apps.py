from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class IcvCoreConfig(AppConfig):
    name = "icv_core"
    label = "icv_core"
    verbose_name = _("ICV Core")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Import the audit models module unconditionally (not gated on
        # ICV_CORE_AUDIT_ENABLED) so Django's app registry discovers
        # AuditEntry, SystemAlert, and AdminActivityLog whenever "icv_core"
        # is installed. The shipped migration (0001_initial) creates these
        # tables unconditionally too; ICV_CORE_AUDIT_ENABLED only gates
        # runtime behaviour, whether audit entries are actually written and
        # whether the login/logout signal handlers connect, never schema.
        #
        # This must NOT be re-exported from icv_core.models.__init__: doing
        # so re-creates the circular import fixed in #14 when a consumer
        # installs "icv_core.audit" directly without "icv_core".
        from icv_core.audit import models as audit_models  # noqa: F401
        from icv_core.conf import ICV_CORE_AUDIT_ENABLED

        from . import (
            checks,  # noqa: F401, register system checks
            handlers,  # noqa: F401, connect signal handlers
        )

        if ICV_CORE_AUDIT_ENABLED:
            from icv_core.audit import handlers as audit_handlers  # noqa: F401
