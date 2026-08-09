# Changelog

All notable changes to django-icv-core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed

- Circular import between `icv_core.models` and `icv_core.audit.models` when
  `icv_core.audit` is added to `INSTALLED_APPS` directly (#14). The
  documented, supported install (`icv_core` in `INSTALLED_APPS` plus
  `ICV_CORE_AUDIT_ENABLED=True`) was never affected; `icv_core.models`
  re-exported `AuditEntry`, `AdminActivityLog`, and `SystemAlert` for
  convenience, and that eager re-export is what forced
  `icv_core.audit.models` to import before `icv_core.models.base` had
  finished defining `BaseModel`. The re-export is removed: nothing in the
  package imported audit models through `icv_core.models` internally, and
  the documented import path has always been `icv_core.audit.models`.
  `icv_core.audit` can now also be installed on its own, without `icv_core`.
- `CurrentUserMiddleware` used `threading.local()` to store the current
  request user, which is not isolated per concurrent request under ASGI: two
  requests running as interleaved `asyncio.Task`s on the same thread (async
  views, or `sync_to_async`-bridged sync views) could observe each other's
  user, corrupting `created_by`/`updated_by` attribution (#13). Replaced with
  `contextvars.ContextVar`, which is isolated per task, and added dual
  sync/async support (`asgiref.sync.iscoroutinefunction`/
  `markcoroutinefunction`) so the middleware no longer forces an
  otherwise-async request pipeline through a sync-only adapter.

### Changed

- `CurrentUserMiddleware` no longer subclasses `MiddlewareMixin` and no
  longer exposes `process_request`/`process_response` as separate hooks;
  it is now a plain dual sync/async middleware callable. `get_current_user()`
  is unaffected. `process_exception` is kept for compatibility with code that
  invokes it directly.

## [0.4.4] - 2026-07-20

### Added

- Per-model UUID version. `VersionedUUIDField` now accepts a `uuid_version`
  argument (and is exported from `icv_core.models`), so a single table can pin
  its primary key to v4 or v7 regardless of the project-wide
  `ICV_CORE_UUID_VERSION`. Opt a high-write table into time-sorted v7 for index
  locality without changing the default, or force v4 on a table whose id is
  public and must not leak a creation timestamp. The override is runtime-only:
  it is not part of the field's deconstruct/migration state, so pinning a
  version generates no migration and preserves the issue-#19 drift fix.

## [0.4.3] - 2026-07-20

### Fixed

- Actually eliminate the family-wide migration drift (umbrella issue #19).
  0.4.2 tried to fix it by making the `_make_uuid` default serialise as
  `uuid.uuid4`, but Django's migration autodetector compares a field's
  deconstructed `default` by object IDENTITY, not by serialised string, so the
  drift persisted (verified against a host with all packages installed: still
  108 `Alter field id` lines). Replaced with a `VersionedUUIDField`
  (`models.UUIDField` subclass): its `deconstruct()` reports a plain
  `django.db.models.UUIDField(default=uuid.uuid4)` (the real `uuid.uuid4`
  object, identity-equal to what every consumer's `0001_initial` ships), while
  its `pre_save()` generates the value via `_make_uuid`, preserving the
  `ICV_CORE_UUID_VERSION` (v4/v7) runtime switch. Installing icv-core alongside
  the family now produces no `Alter field id` drift on any consumer, with no
  consumer re-release. Added migration `0003` realigning icv-core's own audit
  models (whose `0002` recorded `_make_uuid`) back to `uuid.uuid4`; it is
  state-only and emits no SQL. Verified against the deploy host: family UUID
  drift went from 108 lines to 0 (two unrelated per-package migration gaps in
  icv-cms-blocks and icv-media remain, tracked separately).

## [0.4.2] - 2026-07-20

### Fixed

- (Superseded by 0.4.3: this release's migration-serialisation approach did not
  eliminate the drift, see 0.4.3.) Attempted to make the `BaseModel` UUID pk
  default serialise as `uuid.uuid4`; the runtime v4/v7 switch was preserved.
- Package the PEP 561 `py.typed` marker in the built wheel. The marker
  existed on disk but was never declared in `[tool.setuptools.package-data]`,
  so setuptools dropped it from every published wheel and downstream type
  checkers saw `icv_core` as untyped. Now declared and verified present in
  the wheel.

## [0.4.1] - 2026-07-12

### Fixed

- State-only migration 0002 realigning the serialised `id` default on
  `AdminActivityLog`, `AuditEntry`, and `SystemAlert` from `uuid.uuid4`
  to `_make_uuid`, matching the 0.2.0 model change. Emits no SQL and
  needs no database action; it stops `makemigrations --check` reporting
  drift on icv-core's own concrete models. (#1)

### Deprecated

- `icv_core.tenancy` is deprecated and will be removed in 1.0.0; use
  django-boundary (ADR-025 T3). No behaviour change; the module keeps
  working and still emits its `DeprecationWarning` until 1.0.0.

## [0.4.0] - 2026-07-09

### Changed

- Minimum Django is now 5.2 (was 5.0). Django 5.2 and 6.0 are the
  supported and CI-tested versions.
- Packaging: the build backend now requires setuptools 77+ (PEP 639
  SPDX licence metadata) and no longer lists wheel; project URLs point
  at the icvoss GitHub organisation.

## [0.3.0] - 2026-06-24

### Removed

- **`ICV_CORE_SOFT_DELETE_FIELD` setting** (and its `icv_core.E002` system
  check). The setting was inert: the soft-delete marker is the `is_active`
  BooleanField declared on `SoftDeleteModel` (a real, indexed, migrated
  column that cannot be renamed via a setting) and nothing read the setting.
  It only misled consumers into thinking the field was configurable. Setting
  it had no effect before and has no effect now; no migration is required.

### Deprecated

- `icv_core.tenancy` mixins now warn at point of use. Subclassing
  `TenantAwareMixin` or `TenantOwnedMixin` emits a `DeprecationWarning` via
  `__init_subclass__` (precise and actionable, instead of a noisy
  import-time warning on every `icv_core.models` import). The README gains a
  "Tenancy (deprecated)" section with a full migration table to
  `django-boundary` (`TenantModel`, `TenantManager`, `TenantContext`).

## [0.2.0] - 2026-04-08

Promoted to Production/Stable.

### Added

- `ComplianceModel.save()` auto-populates `created_by` (on insert) and
  `updated_by` (on every save) from `CurrentUserMiddleware` when
  `ICV_CORE_TRACK_CREATED_BY` is True. Explicit values are preserved.
- UUID v7 support (RFC 9562): when `ICV_CORE_UUID_VERSION=7`,
  `UUIDModel` generates time-sortable UUIDs using a pure-stdlib
  implementation. No third-party dependency required.
- 28 new tests for ComplianceModel auto-population and UUID v7

### Removed

- Unused `--fix` flag from `icv_core_check` management command

## [0.1.0] - 2026-03-14

### Added

- Abstract base models: `UUIDModel`, `TimestampedModel`, `BaseModel`, `SoftDeleteModel`, `ComplianceModel`
- Custom managers: `SoftDeleteManager` with `deleted()` and `with_deleted()` querysets
- `ScopedManager` for generic filtered queries
- `CurrentUserMiddleware` for `created_by`/`updated_by` tracking
- Soft-delete signals: `pre_soft_delete`, `post_soft_delete`, `pre_restore`, `post_restore`
- `IcvSoftDeleteAdmin` mixin for Django admin
- Package settings via `conf.py` with `ICV_CORE_*` namespace
- Template tags: `cents_to_currency`, `cents_to_amount`, `time_since_short`
- Audit subsystem (gated by `ICV_CORE_AUDIT_ENABLED`):
  - Concrete models: `AuditEntry`, `AdminActivityLog`, `SystemAlert`
  - `AuditMixin` for automatic model change tracking
  - `AuditRequestMiddleware` for request context capture
  - Audit services: `log_event()`, `raise_alert()`, `resolve_alert()`
  - `@audited` decorator for views and service functions
  - Django auth signal handlers (login, logout, login_failed)
  - DRF API viewsets (staff-only)
  - Management commands: `icv_core_check`, `icv_core_audit_archive`, `icv_core_audit_stats`
- Django system checks for configuration validation
- Test utilities: `icv_core.testing` with factories, fixtures, and helpers
- Comprehensive test suite with 90%+ coverage
