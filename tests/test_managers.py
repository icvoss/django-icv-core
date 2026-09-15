"""Tests for icv-core custom managers."""

import pytest
from core_testapp.models import ConcreteScopedModel, ConcreteScopedModelWithoutActive, ConcreteSoftDeleteModel


class TestSoftDeleteManager:
    """SoftDeleteManager filters correctly."""

    @pytest.mark.django_db
    def test_active_returns_only_active(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()

        result = ConcreteSoftDeleteModel.objects.active()
        assert active in result
        assert deleted not in result

    @pytest.mark.django_db
    def test_deleted_returns_only_deleted(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()

        result = ConcreteSoftDeleteModel.objects.deleted()
        assert deleted in result
        assert active not in result

    @pytest.mark.django_db
    def test_with_deleted_returns_all(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()

        result = ConcreteSoftDeleteModel.objects.with_deleted()
        assert active in result
        assert deleted in result


class TestSoftDeleteQuerySet:
    """SoftDeleteQuerySet chaining works correctly."""

    @pytest.mark.django_db
    def test_queryset_active_chained(self):
        ConcreteSoftDeleteModel.objects.create(title="a")
        ConcreteSoftDeleteModel.objects.create(title="b")

        # Default manager already filters active; active() is an alias
        qs = ConcreteSoftDeleteModel.objects.active()
        assert qs.count() == 2

    @pytest.mark.django_db
    def test_queryset_deleted_chained(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="x")
        obj.soft_delete()

        qs = ConcreteSoftDeleteModel.objects.deleted()
        assert qs.count() == 1


class TestSoftDeleteFieldIsFixed:
    """The soft-delete marker is the fixed `is_active` field.

    Regression: ICV_CORE_SOFT_DELETE_FIELD was dead config that implied the
    field name was configurable. It has been removed; setting it must have no
    effect on filtering.
    """

    @pytest.mark.django_db
    def test_filtering_keys_on_is_active(self, settings):
        # A stray setting (as a consumer might still have) must not change behaviour.
        settings.ICV_CORE_SOFT_DELETE_FIELD = "nonexistent_field"

        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()

        assert deleted.is_active is False
        assert active in ConcreteSoftDeleteModel.objects.active()
        assert deleted in ConcreteSoftDeleteModel.objects.deleted()

    def test_setting_is_not_defined_in_conf(self):
        import icv_core.conf as conf

        assert not hasattr(conf, "ICV_CORE_SOFT_DELETE_FIELD")


class TestScopedManager:
    """ScopedManager returns chainable scope-filtered querysets."""

    @pytest.mark.django_db
    def test_for_scope_chains_with_active(self):
        included = ConcreteScopedModel.objects.create(scope="first", is_active=True)
        ConcreteScopedModel.objects.create(scope="first", is_active=False)
        ConcreteScopedModel.objects.create(scope="second", is_active=True)

        result = ConcreteScopedModel.objects.for_scope("scope", "first").active()

        assert list(result) == [included]

    @pytest.mark.django_db
    def test_active_is_unfiltered_without_an_is_active_field(self):
        first = ConcreteScopedModelWithoutActive.objects.create(scope="first")
        second = ConcreteScopedModelWithoutActive.objects.create(scope="second")

        assert set(ConcreteScopedModelWithoutActive.objects.active()) == {first, second}
