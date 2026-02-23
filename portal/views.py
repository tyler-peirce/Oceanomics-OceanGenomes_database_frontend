import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import LabRecordForm, SavedViewForm
from .models import LabRecord, SavedView

DEFAULT_COLUMNS = [
    "sample_code",
    "project",
    "submitter",
    "status",
    "received_at",
    "processed_at",
    "qc_score",
    "read_count",
]


def _is_management_user(user) -> bool:
    return user.is_superuser or user.is_staff or user.groups.filter(name__iexact="management").exists()


@login_required
def dashboard(request):
    records = LabRecord.objects.all()
    total_records = records.count()
    completed_count = records.filter(status=LabRecord.Status.COMPLETED).count()
    pending_count = records.filter(status__in=[LabRecord.Status.RECEIVED, LabRecord.Status.IN_PROGRESS]).count()
    failed_count = records.filter(status=LabRecord.Status.FAILED).count()
    avg_qc = records.aggregate(value=Avg("qc_score"))["value"]

    window_start = timezone.localdate() - timedelta(days=30)
    recent_trend = (
        records.filter(received_at__gte=window_start)
        .annotate(day=TruncDate("received_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )
    trend_labels = [row["day"].isoformat() for row in recent_trend]
    trend_values = [row["total"] for row in recent_trend]

    status_totals = records.values("status").annotate(total=Count("id")).order_by("status")
    status_lookup = dict(LabRecord.Status.choices)
    status_labels = [status_lookup[row["status"]] for row in status_totals]
    status_values = [row["total"] for row in status_totals]

    seven_days_ago = timezone.localdate() - timedelta(days=7)
    overdue_count = records.filter(
        status__in=[LabRecord.Status.RECEIVED, LabRecord.Status.IN_PROGRESS],
        received_at__lt=seven_days_ago,
    ).count()
    low_qc_count = records.filter(qc_score__lt=70).count()

    completion_rate = None
    if total_records:
        completion_rate = round((completed_count / total_records) * 100, 1)

    context = {
        "management_mode": _is_management_user(request.user),
        "total_records": total_records,
        "completed_count": completed_count,
        "pending_count": pending_count,
        "failed_count": failed_count,
        "avg_qc": round(avg_qc, 1) if avg_qc is not None else None,
        "completion_rate": completion_rate,
        "overdue_count": overdue_count,
        "low_qc_count": low_qc_count,
        "recent_records": records.order_by("-received_at", "-id")[:10],
        "status_chart": json.dumps({"labels": status_labels, "values": status_values}),
        "trend_chart": json.dumps({"labels": trend_labels, "values": trend_values}),
    }
    return render(request, "portal/dashboard.html", context)


@login_required
def record_list(request):
    saved_views = SavedView.objects.filter(user=request.user).order_by("-is_default", "name")

    selected_view = None
    selected_view_id = request.GET.get("view")
    if selected_view_id:
        selected_view = get_object_or_404(saved_views, pk=selected_view_id)
    else:
        selected_view = saved_views.filter(is_default=True).first() or saved_views.first()

    queryset = LabRecord.objects.all()
    visible_columns = DEFAULT_COLUMNS

    if selected_view:
        queryset = selected_view.apply_to_queryset(queryset)
        visible_columns = selected_view.visible_columns
    else:
        queryset = queryset.order_by("-received_at")

    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(sample_code__icontains=query)
            | Q(project__icontains=query)
            | Q(submitter__icontains=query)
            | Q(notes__icontains=query)
        )

    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "saved_views": saved_views,
        "selected_view": selected_view,
        "visible_columns": visible_columns,
        "query": query,
    }
    return render(request, "portal/record_list.html", context)


@login_required
def record_create(request):
    if request.method == "POST":
        form = LabRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.created_by = request.user
            record.save()
            messages.success(request, "Record created.")
            return redirect("record_list")
    else:
        form = LabRecordForm()

    return render(request, "portal/record_form.html", {"form": form, "title": "Add Record"})


@login_required
def record_edit(request, pk):
    record = get_object_or_404(LabRecord, pk=pk)

    if request.method == "POST":
        form = LabRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, "Record updated.")
            return redirect("record_list")
    else:
        form = LabRecordForm(instance=record)

    return render(request, "portal/record_form.html", {"form": form, "title": f"Edit {record.sample_code}"})


@login_required
def saved_view_list(request):
    views = SavedView.objects.filter(user=request.user).order_by("-is_default", "name")
    return render(request, "portal/saved_view_list.html", {"views": views})


@login_required
def saved_view_create(request):
    if request.method == "POST":
        form = SavedViewForm(request.POST)
        if form.is_valid():
            saved_view = form.save(commit=False)
            saved_view.user = request.user
            saved_view.save()
            messages.success(request, "Saved view created.")
            return redirect("saved_view_list")
    else:
        form = SavedViewForm(initial={"visible_columns": DEFAULT_COLUMNS})

    return render(request, "portal/saved_view_form.html", {"form": form, "title": "New Saved View"})


@login_required
def saved_view_edit(request, pk):
    saved_view = get_object_or_404(SavedView, pk=pk, user=request.user)

    if request.method == "POST":
        form = SavedViewForm(request.POST, instance=saved_view)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved view updated.")
            return redirect("saved_view_list")
    else:
        form = SavedViewForm(instance=saved_view)

    return render(request, "portal/saved_view_form.html", {"form": form, "title": f"Edit {saved_view.name}"})


@login_required
def saved_view_delete(request, pk):
    saved_view = get_object_or_404(SavedView, pk=pk, user=request.user)

    if request.method == "POST":
        saved_view.delete()
        messages.success(request, "Saved view deleted.")
        return redirect("saved_view_list")

    return render(request, "portal/saved_view_confirm_delete.html", {"saved_view": saved_view})
