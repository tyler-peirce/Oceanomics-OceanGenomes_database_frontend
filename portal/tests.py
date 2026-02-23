from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import LabRecord, SavedView


class LabRecordValidationTests(TestCase):
    def test_processed_date_must_exist_for_completed_status(self):
        record = LabRecord(
            sample_code="LAB-2026-0001",
            submitter="User One",
            project="Oncology",
            received_at=timezone.localdate(),
            status=LabRecord.Status.COMPLETED,
            qc_score=90,
            read_count=100,
        )

        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_processed_date_cannot_be_before_received_date(self):
        today = timezone.localdate()
        record = LabRecord(
            sample_code="LAB-2026-0002",
            submitter="User One",
            project="Oncology",
            received_at=today,
            processed_at=today - timedelta(days=1),
            status=LabRecord.Status.FAILED,
            qc_score=20,
            read_count=100,
        )

        with self.assertRaises(ValidationError):
            record.full_clean()


class SavedViewBehaviorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="password123")

    def test_first_saved_view_becomes_default(self):
        view = SavedView.objects.create(
            user=self.user,
            name="Primary",
            visible_columns=["sample_code", "status"],
            ordering="-received_at",
            is_default=False,
        )
        self.assertTrue(view.is_default)

    def test_setting_new_default_unsets_previous_default(self):
        first = SavedView.objects.create(
            user=self.user,
            name="Primary",
            visible_columns=["sample_code", "status"],
            ordering="-received_at",
            is_default=True,
        )
        second = SavedView.objects.create(
            user=self.user,
            name="Secondary",
            visible_columns=["sample_code", "project"],
            ordering="sample_code",
            is_default=True,
        )

        first.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)
