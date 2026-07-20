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


def _make_uuid() -> uuid.UUID:
    """
    Return a UUID whose version is determined by ``ICV_CORE_UUID_VERSION``.

    The setting is read at call time so that test overrides via ``pytest``
    ``settings`` fixtures take effect without requiring a module reload.
    """
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

    The version is a per-deployment performance choice (a runtime setting), not
    a data-model fact to bake into immutable migrations, so reporting the
    stable ``uuid.uuid4`` in migrations is the correct, faithful serialisation.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        # Report a plain uuid.uuid4 default in deconstruct/migrations; the real
        # value is produced by pre_save below.
        kwargs.setdefault("default", uuid.uuid4)
        super().__init__(*args, **kwargs)

    def pre_save(self, model_instance: models.Model, add: bool):
        value = super().pre_save(model_instance, add)
        # On insert with no explicit value, honour the runtime version switch
        # instead of the plain uuid.uuid4 default carried for migration parity.
        if add and not getattr(model_instance, self.attname, None):
            value = _make_uuid()
            setattr(model_instance, self.attname, value)
        return value

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        # Freeze as a vanilla UUIDField(default=uuid.uuid4) so consumers'
        # existing migrations match exactly (path + default object identity).
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
    """

    class Meta:
        abstract = True
        ordering = ["-created_at"]
