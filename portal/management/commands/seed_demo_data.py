from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from portal.models import LabRecord, SavedView


class Command(BaseCommand):
    help = "Create demo users, records, and a default saved view."

    def handle(self, *args, **options):
        user_model = get_user_model()
        analyst, _ = user_model.objects.get_or_create(
            username="lab_analyst",
            defaults={"email": "lab_analyst@example.com"},
        )
        analyst.set_password("ChangeMe123!")
        analyst.save()

        today = timezone.localdate()
        demo_rows = [
            {
                "sample_code": "LAB-2026-0001",
                "submitter": "A. James",
                "project": "Cancer Genomics",
                "received_at": today - timedelta(days=10),
                "processed_at": today - timedelta(days=7),
                "status": LabRecord.Status.COMPLETED,
                "qc_score": 92,
                "read_count": 48600000,
                "notes": "Passed all QC checks.",
            },
            {
                "sample_code": "LAB-2026-0002",
                "submitter": "M. Patel",
                "project": "Metagenomics",
                "received_at": today - timedelta(days=5),
                "processed_at": None,
                "status": LabRecord.Status.IN_PROGRESS,
                "qc_score": 77,
                "read_count": 33210000,
                "notes": "Awaiting final pipeline output.",
            },
            {
                "sample_code": "LAB-2026-0003",
                "submitter": "L. Brown",
                "project": "Rare Disease",
                "received_at": today - timedelta(days=2),
                "processed_at": None,
                "status": LabRecord.Status.RECEIVED,
                "qc_score": 81,
                "read_count": 0,
                "notes": "Queued for extraction.",
            },
        ]

        for row in demo_rows:
            LabRecord.objects.update_or_create(
                sample_code=row["sample_code"],
                defaults={**row, "created_by": analyst},
            )

        SavedView.objects.update_or_create(
            user=analyst,
            name="High QC Only",
            defaults={
                "visible_columns": [
                    "sample_code",
                    "project",
                    "status",
                    "received_at",
                    "qc_score",
                    "read_count",
                ],
                "status_filter": "",
                "min_qc_score": 80,
                "ordering": "-qc_score",
                "is_default": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo data loaded. User: lab_analyst / password: ChangeMe123!"))
