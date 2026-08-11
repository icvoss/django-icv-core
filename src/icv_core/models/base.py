"""Abstract base models for all ICV-Django packages."""

import logging
import os
import time
import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def _uuid7() -> uuid.UUID:
    """
    Generate a UUID version 7 value per RFC 9562.

    Layout (128 bits):
      unix_ts_ms  — 48 bits  — milliseconds since Unix epoch
      ver         —  4 bits  — version = 0b0111 (7)
      rand_a      — 12 bits  — random
      var         —  2 bits  — variant = 0b10
      rand_b      — 62 bits  — random

    Python 3.12 does not include uuid.uuid7(); this implementation uses only
    the stdlib uuid and os modules.
    """
    ms = int(time.time() * 1000) & 0xFFFF_FFFF_FFFF  # 48-bit timestamp
    rand = int.from_bytes(os.urandom(10), "big")  # 80 random bits
    rand_a = (rand >> 68) & 0xFFF  # upper 12 bits
    rand_b = rand & 0x3FFF_FFFF_FFFF_FFFF  # lower 62 bits

    hi = (ms << 16) | 0x7000 | rand_a  # 64 bits: ts + ver + rand_a
    lo = 0x8000_0000_0000_0000 | rand_b  # 64 bits: var + rand_b

    return uuid.UUID(int=(hi << 64) | lo)


def _make_uuid(version: int | None = None) -> uuid.UUID:
    """
    Return a UUID whose version is determined by ``version`` if given, else by
    the project-wide ``ICV_CORE_UUID_VERSION`` setting.

    An explicit ``version`` lets a single field opt into v7 (or v4) regardless
    of the project default (see ``VersionedUUIDField(uuid_version=...)``). When
    ``version`` is ``None`` the setting is read at call time, so test overrides
    via ``pytest`` ``settings`` fixtures take effect without a module reload.
    """
    if version is None:
        from icv_core.conf import get_setting

        version = get_setting("UUID_VERSION", 4)
    if version == 7:
        return _uuid7()
    return uuid.uuid4()


class VersionedUUIDField(models.UUIDField):
    """
    A UUID primary-key field that is UUID-version agnostic in migrations but
    honours ``ICV_CORE_UUID_VERSION`` at runtime.

    Why this exists (umbrella issue #19): every icvoss package that uses
    ``BaseModel`` ships ``0001_initial`` migrations declaring
    ``default=uuid.uuid4`` (they were generated without icv-core installed).
    If icv-core's pk field carried ``default=_make_uuid``, then installing
    icv-core alongside those packages makes their runtime model default differ
    from their own shipped migration, and Django's autodetector demands an
    ``Alter field id`` on every model in every consumer. Crucially, matching
    only the *serialised name* is not enough: the autodetector compares the
    deconstructed ``default`` by object identity, so a callable that merely
    prints as ``uuid.uuid4`` is still seen as a change.

    This field solves it at the right layer:
      - ``deconstruct()`` reports a plain ``django.db.models.UUIDField`` with
        ``default=uuid.uuid4`` (the real object), so it is byte-identical AND
        identity-identical to what consumers already ship, no drift, no
        consumer re-release.
      - ``pre_save()`` generates the value via ``_make_uuid`` (the
        ``ICV_CORE_UUID_VERSION`` v4/v7 switch), so the runtime behaviour is
        preserved.

    The version is a runtime choice, not a data-model fact to bake into
    immutable migrations, so reporting the stable ``uuid.uuid4`` in migrations
    is the correct, faithful serialisation.

    Per-model override: pass ``uuid_version=7`` (or ``4``) to pin a specific
    table's pk to that version regardless of ``ICV_CORE_UUID_VERSION``. This is
    the useful shape, opt a high-write table (events, audit logs, orders) into
    time-sorted v7 for index locality without changing the project default, or
    forcing v4 on a table whose id is public and must not leak a timestamp. The
    override is a runtime-only attribute: it does NOT appear in ``deconstruct()``
    (the field still freezes as ``UUIDField(default=uuid.uuid4)``), so pinning a
    version generates no migration and keeps the issue-#19 drift fix intact.

    A model opts in by overriding the inherited pk::

        from icv_core.models import BaseModel
        from icv_core.models.base import VersionedUUIDField

        class SiteEvent(BaseModel):
            id = VersionedUUIDField(primary_key=True, editable=False, uuid_version=7)
    """

    def __init__(self, *args: object, uuid_version: int | None = None, **kwargs: object) -> None:
        # Per-field version override (None = follow the ICV_CORE_UUID_VERSION
        # setting at insert time). Runtime-only; deliberately not serialised.
        self.uuid_version = uuid_version
        # Report a plain uuid.uuid4 default in deconstruct/migrations; the real
        # value is produced by pre_save below.
        kwargs.setdefault("default", uuid.uuid4)
        super().__init__(*args, **kwargs)

    def pre_save(self, model_instance: models.Model, add: bool):
        value = super().pre_save(model_instance, add)
        # On insert with no explicit value, honour the version switch (this
        # field's uuid_version override if set, else the project setting)
        # instead of the plain uuid.uuid4 default carried for migration parity.
        if add and not getattr(model_instance, self.attname, None):
            value = _make_uuid(version=self.uuid_version)
            setattr(model_instance, self.attname, value)
        return value

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        # Freeze as a vanilla UUIDField(default=uuid.uuid4) so consumers'
        # existing migrations match exactly (path + default object identity).
        # uuid_version is runtime-only and intentionally omitted, pinning a
        # version must not produce a migration.
        return name, "django.db.models.UUIDField", args, kwargs


class UUIDModel(models.Model):
    """Abstract model providing a UUID primary key."""

    id = VersionedUUIDField(
        primary_key=True,
        editable=False,
        verbose_name=_("ID"),
    )

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    """Abstract model with auto-managed created_at and updated_at timestamps."""

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("created at"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("updated at"),
    )

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimestampedModel):
    """
    Standard base model combining a UUID primary key and auto-managed timestamps.

    All ICV-Django concrete models should inherit from this unless there is a
    specific reason not to (e.g., an append-only log table that must not have
    updated_at).

    Deliberately sets no default ordering (ADR-066): a ``Meta.ordering`` on a
    shared base defeats ``values()``/``values_list()`` combined with
    ``distinct()`` in every inheriting model, so order explicitly at the call
    site or in the subclass ``Meta`` instead.
    """

    class Meta:
        abstract = True
