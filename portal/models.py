from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone


class LabRecord(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    sample_code = models.CharField(
        max_length=32,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{2,6}-\d{4}-\d{3,6}$",
                message="Use sample code format like LAB-2026-0001.",
            )
        ],
        help_text="Format: PREFIX-YYYY-NNNN (example: LAB-2026-0001)",
    )
    submitter = models.CharField(max_length=120)
    project = models.CharField(max_length=120)
    received_at = models.DateField(default=timezone.localdate)
    processed_at = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED)
    qc_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="QC score between 0 and 100.",
    )
    read_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(processed_at__isnull=True) | Q(processed_at__gte=F("received_at")),
                name="processed_after_received",
            ),
            models.CheckConstraint(
                condition=Q(qc_score__gte=0) & Q(qc_score__lte=100),
                name="qc_score_in_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sample_code} ({self.get_status_display()})"

    def clean(self) -> None:
        errors = {}
        today = timezone.localdate()

        if self.received_at and self.received_at > today:
            errors["received_at"] = "Received date cannot be in the future."

        if self.processed_at and self.received_at and self.processed_at < self.received_at:
            errors["processed_at"] = "Processed date cannot be earlier than received date."

        if self.status in {self.Status.COMPLETED, self.Status.FAILED} and not self.processed_at:
            errors["processed_at"] = "Processed date is required when status is completed or failed."

        if errors:
            raise ValidationError(errors)

    @property
    def turnaround_days(self):
        if self.processed_at and self.received_at:
            return (self.processed_at - self.received_at).days
        return None

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class SavedView(models.Model):
    COLUMN_CHOICES = [
        ("sample_code", "Sample Code"),
        ("project", "Project"),
        ("submitter", "Submitter"),
        ("status", "Status"),
        ("received_at", "Received"),
        ("processed_at", "Processed"),
        ("qc_score", "QC Score"),
        ("read_count", "Read Count"),
    ]

    ORDERING_CHOICES = [
        ("-received_at", "Newest received first"),
        ("received_at", "Oldest received first"),
        ("-qc_score", "Highest QC first"),
        ("qc_score", "Lowest QC first"),
        ("sample_code", "Sample code A-Z"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_views")
    name = models.CharField(max_length=100)
    visible_columns = models.JSONField(default=list)
    status_filter = models.CharField(
        max_length=16,
        choices=[("", "All statuses"), *LabRecord.Status.choices],
        blank=True,
    )
    min_qc_score = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    ordering = models.CharField(max_length=32, choices=ORDERING_CHOICES, default="-received_at")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_saved_view_name_per_user"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.user.username})"

    def clean(self) -> None:
        valid_columns = {value for value, _ in self.COLUMN_CHOICES}
        chosen = set(self.visible_columns or [])

        if not chosen:
            raise ValidationError({"visible_columns": "Select at least one column."})

        invalid = chosen - valid_columns
        if invalid:
            invalid_list = ", ".join(sorted(invalid))
            raise ValidationError({"visible_columns": f"Unsupported columns: {invalid_list}"})

    def save(self, *args, **kwargs):
        self.full_clean()

        with transaction.atomic():
            if self.is_default:
                SavedView.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)

            if not self.is_default and not SavedView.objects.filter(user=self.user).exclude(pk=self.pk).exists():
                self.is_default = True

            return super().save(*args, **kwargs)

    def apply_to_queryset(self, queryset):
        if self.status_filter:
            queryset = queryset.filter(status=self.status_filter)

        if self.min_qc_score is not None:
            queryset = queryset.filter(qc_score__gte=self.min_qc_score)

        return queryset.order_by(self.ordering)
