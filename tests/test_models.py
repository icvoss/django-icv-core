"""Tests for icv-core abstract base models."""

import uuid

import pytest
from core_testapp.models import ConcreteBaseModel, ConcreteSoftDeleteModel
from django.db import models

from icv_core.models import BaseModel, SoftDeleteModel, TimestampedModel, UUIDModel


class TestUUIDModel:
    """UUIDModel provides a UUID primary key."""

    def test_has_uuid_primary_key(self):
        field = UUIDModel._meta.get_field("id")
        assert isinstance(field, models.UUIDField)
        assert field.primary_key is True
        assert field.editable is False

    def test_default_is_callable(self):
        field = UUIDModel._meta.get_field("id")
        assert callable(field.default)

    def test_generated_pk_is_valid_uuid(self):
        field = ConcreteBaseModel._meta.get_field("id")
        value = field.default()
        assert isinstance(value, uuid.UUID)

    def test_default_uuid_version_is_4(self):
        """Without any setting override, _make_uuid() returns a v4 UUID."""
        from icv_core.models.base import _make_uuid

        value = _make_uuid()
        assert isinstance(value, uuid.UUID)
        assert value.version == 4

    def test_pk_field_deconstructs_as_plain_uuidfield_default_uuid4(self):
        """The pk field MUST deconstruct as ``UUIDField(default=uuid.uuid4)``.

        This is the layer Django's autodetector actually compares (issue #19).
        Every icvoss package ships ``0001_initial`` migrations declaring a plain
        ``models.UUIDField(default=uuid.uuid4)``. The autodetector compares the
        deconstructed field by path + the ``default`` object's IDENTITY, so it
        is not enough for a callable to merely serialise as ``uuid.uuid4``: the
        field must deconstruct to the vanilla path with the REAL ``uuid.uuid4``
        object. ``VersionedUUIDField`` does exactly that, so installing icv-core
        alongside a consumer produces no ``Alter field id`` drift.
        """
        field = UUIDModel._meta.get_field("id")
        _name, path, _args, kwargs = field.deconstruct()
        assert path == "django.db.models.UUIDField"
        # Same object, not merely same repr: this is what the autodetector uses.
        assert kwargs["default"] is uuid.uuid4

    def test_pk_field_honours_version_switch_at_pre_save(self, settings):
        """VersionedUUIDField still honours ICV_CORE_UUID_VERSION at insert.

        The migration parity (default=uuid.uuid4) must not cost the runtime
        v4/v7 switch: pre_save generates the value via _make_uuid.
        """
        field = ConcreteBaseModel._meta.get_field("id")

        settings.ICV_CORE_UUID_VERSION = 7
        instance = ConcreteBaseModel()
        instance.id = None
        assert field.pre_save(instance, add=True).version == 7

        settings.ICV_CORE_UUID_VERSION = 4
        instance2 = ConcreteBaseModel()
        instance2.id = None
        assert field.pre_save(instance2, add=True).version == 4

    def test_per_field_uuid_version_overrides_the_global_setting(self, settings):
        """``VersionedUUIDField(uuid_version=7)`` pins a table to v7.

        A per-field override wins over ``ICV_CORE_UUID_VERSION`` at insert
        time, so one model can use v7 while the project default stays v4 (and
        vice versa).
        """
        from icv_core.models.base import VersionedUUIDField

        class _Dummy:
            pass

        settings.ICV_CORE_UUID_VERSION = 4  # project default is v4

        v7_field = VersionedUUIDField(primary_key=True, uuid_version=7)
        v7_field.attname = "id"
        inst = _Dummy()
        inst.id = None
        assert v7_field.pre_save(inst, add=True).version == 7  # override wins

        v4_field = VersionedUUIDField(primary_key=True, uuid_version=4)
        v4_field.attname = "id"
        settings.ICV_CORE_UUID_VERSION = 7  # project default now v7
        inst2 = _Dummy()
        inst2.id = None
        assert v4_field.pre_save(inst2, add=True).version == 4  # override wins

    def test_per_field_uuid_version_is_not_serialised(self):
        """The ``uuid_version`` override must NOT appear in deconstruct().

        Pinning a version is a runtime choice; it must not change the field's
        migration state (still a plain ``UUIDField(default=uuid.uuid4)``), so it
        generates no migration and preserves the issue-#19 drift fix.
        """
        import uuid as _uuid

        from icv_core.models.base import VersionedUUIDField

        field = VersionedUUIDField(primary_key=True, editable=False, uuid_version=7)
        _name, path, _args, kwargs = field.deconstruct()
        assert path == "django.db.models.UUIDField"
        assert kwargs["default"] is _uuid.uuid4
        assert "uuid_version" not in kwargs

    def test_uuid_version_7_returns_v7(self, settings):
        """When ICV_CORE_UUID_VERSION=7 is set, _make_uuid() returns a v7 UUID."""
        settings.ICV_CORE_UUID_VERSION = 7

        from icv_core.models.base import _make_uuid

        value = _make_uuid()
        assert isinstance(value, uuid.UUID)
        assert value.version == 7

    def test_uuid_v7_timestamp_is_non_decreasing(self, settings):
        """The 48-bit ms-timestamp embedded in successive v7 UUIDs must never go backwards."""
        settings.ICV_CORE_UUID_VERSION = 7

        from icv_core.models.base import _make_uuid

        values = [_make_uuid() for _ in range(20)]
        # The top 48 bits of the UUID int encode the millisecond timestamp.
        timestamps = [v.int >> 80 for v in values]
        assert timestamps == sorted(timestamps)


class TestTimestampedModel:
    """TimestampedModel provides created_at and updated_at."""

    def test_has_created_at(self):
        field = TimestampedModel._meta.get_field("created_at")
        assert isinstance(field, models.DateTimeField)
        assert field.auto_now_add is True

    def test_has_updated_at(self):
        field = TimestampedModel._meta.get_field("updated_at")
        assert isinstance(field, models.DateTimeField)
        assert field.auto_now is True

    def test_created_at_has_db_index(self):
        field = TimestampedModel._meta.get_field("created_at")
        assert field.db_index is True


class TestBaseModel:
    """BaseModel combines UUID PK and timestamps."""

    def test_is_abstract(self):
        assert BaseModel._meta.abstract is True

    def test_has_uuid_pk(self):
        field = ConcreteBaseModel._meta.get_field("id")
        assert isinstance(field, models.UUIDField)
        assert field.primary_key is True

    def test_has_timestamps(self):
        assert ConcreteBaseModel._meta.get_field("created_at")
        assert ConcreteBaseModel._meta.get_field("updated_at")

    def test_no_default_ordering(self):
        # BaseModel deliberately sets no default ordering (ADR-066): a
        # Meta.ordering on a shared base defeats values()/values_list()
        # combined with distinct() in every inheriting model. Models needing
        # a default order declare it themselves.
        assert BaseModel._meta.ordering == []

    def test_inherits_uuid_and_timestamp(self):
        field_names = [f.name for f in ConcreteBaseModel._meta.fields]
        assert "id" in field_names
        assert "created_at" in field_names
        assert "updated_at" in field_names


class TestSoftDeleteModel:
    """SoftDeleteModel adds soft-delete behaviour to BaseModel."""

    def test_is_abstract(self):
        assert SoftDeleteModel._meta.abstract is True

    def test_has_is_active_field(self):
        field = ConcreteSoftDeleteModel._meta.get_field("is_active")
        assert isinstance(field, models.BooleanField)
        assert field.default is True
        assert field.db_index is True

    def test_has_deleted_at_field(self):
        field = ConcreteSoftDeleteModel._meta.get_field("deleted_at")
        assert isinstance(field, models.DateTimeField)
        assert field.null is True
        assert field.blank is True

    def test_has_soft_delete_manager(self):
        from icv_core.managers import SoftDeleteManager

        assert isinstance(ConcreteSoftDeleteModel.objects, SoftDeleteManager)

    def test_has_all_objects_manager(self):
        assert isinstance(ConcreteSoftDeleteModel.all_objects, models.Manager)

    @pytest.mark.django_db
    def test_soft_delete_sets_is_active_false(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        obj.soft_delete()
        obj.refresh_from_db()
        assert obj.is_active is False

    @pytest.mark.django_db
    def test_soft_delete_sets_deleted_at(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        assert obj.deleted_at is None
        obj.soft_delete()
        obj.refresh_from_db()
        assert obj.deleted_at is not None

    @pytest.mark.django_db
    def test_restore_sets_is_active_true(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        obj.soft_delete()
        obj.restore()
        obj.refresh_from_db()
        assert obj.is_active is True

    @pytest.mark.django_db
    def test_restore_clears_deleted_at(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        obj.soft_delete()
        obj.restore()
        obj.refresh_from_db()
        assert obj.deleted_at is None

    @pytest.mark.django_db
    def test_default_manager_excludes_soft_deleted(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()
        qs = ConcreteSoftDeleteModel.objects.all()
        assert active in qs
        assert deleted not in qs

    @pytest.mark.django_db
    def test_all_objects_includes_soft_deleted(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()
        qs = ConcreteSoftDeleteModel.all_objects.all()
        assert active in qs
        assert deleted in qs

    @pytest.mark.django_db
    def test_delete_raises_protected_error_by_default(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        with pytest.raises(models.ProtectedError):
            obj.delete()

    @pytest.mark.django_db
    def test_delete_allowed_when_setting_enabled(self, allow_hard_delete):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        obj_pk = obj.pk
        obj.delete()
        assert not ConcreteSoftDeleteModel.all_objects.filter(pk=obj_pk).exists()

    @pytest.mark.django_db
    def test_hard_delete_bypasses_protection(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="test")
        obj_pk = obj.pk
        obj.hard_delete()
        assert not ConcreteSoftDeleteModel.all_objects.filter(pk=obj_pk).exists()

    @pytest.mark.django_db
    def test_soft_delete_emits_signals(self):
        from icv_core.signals import post_soft_delete, pre_soft_delete

        pre_received = []
        post_received = []

        def on_pre(sender, instance, **kwargs):
            pre_received.append(instance)

        def on_post(sender, instance, **kwargs):
            post_received.append(instance)

        pre_soft_delete.connect(on_pre)
        post_soft_delete.connect(on_post)

        obj = ConcreteSoftDeleteModel.objects.create(title="signal-test")
        obj.soft_delete()

        pre_soft_delete.disconnect(on_pre)
        post_soft_delete.disconnect(on_post)

        assert len(pre_received) == 1
        assert len(post_received) == 1
        assert pre_received[0] is obj

    @pytest.mark.django_db
    def test_restore_emits_signals(self):
        from icv_core.signals import post_restore, pre_restore

        pre_received = []
        post_received = []

        def on_pre(sender, instance, **kwargs):
            pre_received.append(instance)

        def on_post(sender, instance, **kwargs):
            post_received.append(instance)

        pre_restore.connect(on_pre)
        post_restore.connect(on_post)

        obj = ConcreteSoftDeleteModel.objects.create(title="restore-signal-test")
        obj.soft_delete()
        obj.restore()

        pre_restore.disconnect(on_pre)
        post_restore.disconnect(on_post)

        assert len(pre_received) == 1
        assert len(post_received) == 1
