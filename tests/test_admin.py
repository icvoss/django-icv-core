"""Consumer-facing tests for the soft-delete admin mixin."""

import pytest
from core_testapp.models import ConcreteSoftDeleteModel
from django.contrib import admin
from django.test import RequestFactory

from icv_core.admin import IcvSoftDeleteAdmin


@pytest.mark.django_db
class TestIcvSoftDeleteAdmin:
    def setup_method(self, method):
        self.model_admin = IcvSoftDeleteAdmin(ConcreteSoftDeleteModel, admin.site)
        self.request = RequestFactory().get("/admin/core_testapp/concretesoftdeletemodel/")

    def test_get_queryset_includes_soft_deleted_records(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        deleted = ConcreteSoftDeleteModel.objects.create(title="deleted")
        deleted.soft_delete()

        assert set(self.model_admin.get_queryset(self.request)) == {active, deleted}

    def test_actions_apply_the_model_lifecycle_to_the_matching_rows(self):
        active = ConcreteSoftDeleteModel.objects.create(title="active")
        inactive = ConcreteSoftDeleteModel.objects.create(title="inactive")
        inactive.soft_delete()

        self.model_admin.soft_delete_selected(
            self.request,
            ConcreteSoftDeleteModel.all_objects.filter(pk__in=[active.pk, inactive.pk]),
        )
        active.refresh_from_db()
        inactive.refresh_from_db()
        assert active.is_active is False
        assert inactive.is_active is False

        self.model_admin.restore_selected(
            self.request,
            ConcreteSoftDeleteModel.all_objects.filter(pk__in=[active.pk, inactive.pk]),
        )
        active.refresh_from_db()
        inactive.refresh_from_db()
        assert active.is_active is True
        assert inactive.is_active is True
