from icv_core.models.base import BaseModel, TimestampedModel, UUIDModel, VersionedUUIDField
from icv_core.models.compliance import ComplianceModel
from icv_core.models.soft_delete import SoftDeleteModel

# Tenancy mixins: DEPRECATED. Use boundary.models.TenantModel instead.
# Kept for backwards compatibility; will be removed in a future release.
from icv_core.tenancy.mixins import TenantAwareMixin, TenantOwnedMixin

# Audit models (AuditEntry, AdminActivityLog, SystemAlert) live under
# icv_core.audit.models and carry app_label="icv_core", but are deliberately
# NOT re-exported here. They must not be imported from this module: doing so
# forces icv_core.audit.models to import while icv_core.models is still
# mid-init, which is a circular import (icv_core.audit.models imports
# BaseModel from icv_core.models.base, one line below this file's own import
# of icv_core.audit.models). Django's app registry discovers them without
# this re-export, because Django imports each installed app's models module
# directly (AppConfig.import_models), not via icv_core.models. Consumers
# import audit models from icv_core.audit.models, as documented in the
# package README and 04-interfaces.md.
__all__ = [
    "UUIDModel",
    "TimestampedModel",
    "BaseModel",
    "VersionedUUIDField",
    "SoftDeleteModel",
    "ComplianceModel",
    # tenancy
    "TenantAwareMixin",
    "TenantOwnedMixin",
]
