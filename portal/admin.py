from django.contrib import admin

from .models import LabRecord, SavedView


@admin.register(LabRecord)
class LabRecordAdmin(admin.ModelAdmin):
    list_display = (
        "sample_code",
        "project",
        "submitter",
        "status",
        "qc_score",
        "received_at",
        "processed_at",
    )
    list_filter = ("status", "project", "received_at")
    search_fields = ("sample_code", "project", "submitter", "notes")


@admin.register(SavedView)
class SavedViewAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "is_default", "status_filter", "min_qc_score", "ordering")
    list_filter = ("is_default", "status_filter")
    search_fields = ("name", "user__username")
