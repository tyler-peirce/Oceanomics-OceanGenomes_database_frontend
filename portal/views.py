import json
from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .data_access import build_row_detail_url, count_relation_rows, fetch_relation_page, fetch_row_detail
from .forms import RnaExtractionForm, SampleIntakeForm, SavedJoinedViewForm, SavedTableViewForm
from .joined_views import fetch_joined_view_page, hidden_base_pk_alias, joined_view_display_columns
from .models import SavedJoinedView, SavedTableView
from .presets import get_featured_lab_presets, get_lab_preset, get_lab_presets, get_table_lab_presets
from .rna_extractions import (
    RNA_EXTRACTION_LIST_COLUMNS,
    RNA_EXTRACTION_FIELD_DEFINITIONS_BY_NAME,
    RNA_EXTRACTION_INLINE_EDITABLE_COLUMNS,
    WORKBOOK_UNMAPPED_RNA_FIELDS,
    bulk_update_rna_extractions,
    create_rna_extraction_record,
    fetch_rna_extraction_page,
    fetch_rna_extraction_record,
    resolve_rna_identity,
    rna_extraction_column_label,
    update_rna_extraction_record,
)
from .sample_metadata import (
    SAMPLE_LIST_COLUMNS,
    SAMPLE_FIELD_DEFINITIONS_BY_NAME,
    SAMPLE_INLINE_EDITABLE_COLUMNS,
    WORKBOOK_UNMAPPED_METADATA_FIELDS,
    bulk_update_sample_metadata,
    create_sample_metadata_record,
    fetch_sample_metadata_page,
    fetch_sample_metadata_record,
    sample_column_label,
    update_sample_metadata_record,
)
from .schema import SchemaMetadataError, get_schema_catalog, get_table_metadata
from .workbook import build_worksheet_tabs, detect_active_worksheet

PAGE_SIZE = 25
FOCUS_TABLES = (
    "sample",
    "tissue",
    "dna_extraction",
    "rna_extraction",
    "sequencing",
    "summary",
)


def _safe_page_number(value: str | None) -> int:
    try:
        return max(int(value or "1"), 1)
    except (TypeError, ValueError):
        return 1


def _current_query_without(request, *keys: str) -> str:
    params = request.GET.copy()
    for key in keys:
        params.pop(key, None)
    return params.urlencode()


def _ordering_options(table) -> list[tuple[str, str]]:
    options = [("", "Natural order")]
    for column_name in table.ordered_column_names:
        options.append((column_name, f"{column_name} (ascending)"))
        options.append((f"-{column_name}", f"{column_name} (descending)"))
    return options


def _worksheet_context(active_slug: str | None = None) -> dict:
    return {"worksheet_tabs": build_worksheet_tabs(active_slug)}


def _selected_saved_view(request, table_name: str):
    saved_views = SavedTableView.objects.filter(
        user=request.user,
        table_name=table_name,
    ).order_by("-is_default", "name")

    selected_view_id = request.GET.get("view")
    if selected_view_id:
        selected_view = get_object_or_404(saved_views, pk=selected_view_id)
    elif request.GET.get("preset"):
        selected_view = None
    else:
        selected_view = saved_views.filter(is_default=True).first() or saved_views.first()
    return saved_views, selected_view


@login_required
def dashboard(request):
    try:
        catalog = list(get_schema_catalog())
    except SchemaMetadataError as exc:
        return render(request, "portal/dashboard.html", {"schema_error": str(exc)})

    relation_counts = Counter(table.relation_kind for table in catalog)
    widest_relations = sorted(catalog, key=lambda table: table.column_count, reverse=True)[:8]
    focus_tables = []
    for table_name in FOCUS_TABLES:
        matching_table = next((table for table in catalog if table.name == table_name), None)
        if matching_table:
            focus_tables.append(
                {
                    "table": matching_table,
                    "row_count": count_relation_rows(matching_table),
                }
            )
    workflow_presets = []
    for preset in get_featured_lab_presets():
        matching_table = next((table for table in catalog if table.name == preset.table_name), None)
        if matching_table:
            workflow_presets.append(
                {
                    "preset": preset,
                    "table": matching_table,
                }
            )

    context = {
        "total_relations": len(catalog),
        "base_table_count": relation_counts.get("table", 0),
        "view_count": relation_counts.get("view", 0),
        "total_columns": sum(table.column_count for table in catalog),
        "relations_with_primary_keys": sum(1 for table in catalog if table.has_primary_key),
        "relations_with_foreign_keys": sum(1 for table in catalog if table.has_foreign_keys),
        "widest_relation": widest_relations[0] if widest_relations else None,
        "focus_tables": focus_tables,
        "recent_relations": catalog[:10],
        "workflow_presets": workflow_presets,
        "relation_kind_chart": json.dumps(
            {
                "labels": ["Tables", "Views"],
                "values": [relation_counts.get("table", 0), relation_counts.get("view", 0)],
            }
        ),
        "width_chart": json.dumps(
            {
                "labels": [table.name for table in widest_relations],
                "values": [table.column_count for table in widest_relations],
            }
        ),
    }
    context.update(_worksheet_context())
    return render(request, "portal/dashboard.html", context)


@login_required
def table_list(request):
    try:
        catalog = list(get_schema_catalog())
    except SchemaMetadataError as exc:
        return render(request, "portal/table_list.html", {"schema_error": str(exc), "table_entries": []})

    query = request.GET.get("q", "").strip().lower()
    if query:
        catalog = [
            table
            for table in catalog
            if query in table.name.lower()
            or any(query in column.lower() for column in table.ordered_column_names)
        ]

    default_views = {
        saved_view.table_name: saved_view
        for saved_view in SavedTableView.objects.filter(user=request.user, is_default=True)
    }
    table_entries = []
    for table in catalog:
        table_entries.append(
            {
                "table": table,
                "default_view": default_views.get(table.name),
                "lab_presets": get_table_lab_presets(table.name),
                "preview_columns": ", ".join(table.ordered_column_names[:4]),
            }
        )

    context = {
        "table_entries": table_entries,
        "query": request.GET.get("q", "").strip(),
    }
    context.update(_worksheet_context())
    return render(request, "portal/table_list.html", context)


@login_required
def table_detail(request, table_name: str):
    try:
        table = get_table_metadata(table_name)
    except SchemaMetadataError as exc:
        raise Http404(str(exc)) from exc

    saved_views, selected_view = _selected_saved_view(request, table_name)
    selected_preset = None
    preset_slug = request.GET.get("preset", "").strip()
    if preset_slug and not request.GET.get("view"):
        selected_preset = get_lab_preset(preset_slug)
        if selected_preset and selected_preset.table_name != table_name:
            selected_preset = None

    requested_columns = request.GET.getlist("columns")
    visible_columns = requested_columns or (
        selected_view.visible_columns
        if selected_view
        else selected_preset.visible_columns
        if selected_preset
        else table.default_visible_columns
    )
    visible_columns = [column for column in visible_columns if column in table.ordered_column_names]
    if not visible_columns:
        visible_columns = table.default_visible_columns

    ordering = request.GET.get("ordering") or (
        selected_view.ordering
        if selected_view
        else selected_preset.ordering
        if selected_preset
        else ""
    )
    query = request.GET.get("q", "").strip()
    page_number = _safe_page_number(request.GET.get("page"))

    relation_page = fetch_relation_page(
        table=table,
        visible_columns=visible_columns,
        search_query=query,
        ordering=ordering,
        page_number=page_number,
        page_size=PAGE_SIZE,
    )
    page_obj = Paginator(range(relation_page.total_count), PAGE_SIZE).get_page(page_number)

    rows = []
    for raw_row in relation_page.rows:
        rows.append(
            {
                "cells": [raw_row.get(column_name) for column_name in visible_columns],
                "detail_url": build_row_detail_url(table, raw_row),
            }
        )

    context = {
        "table": table,
        "rows": rows,
        "visible_columns": visible_columns,
        "saved_views": saved_views,
        "table_presets": get_table_lab_presets(table_name),
        "selected_view": selected_view,
        "selected_preset": selected_preset,
        "ordering": ordering,
        "ordering_options": _ordering_options(table),
        "query": query,
        "page_obj": page_obj,
        "pagination_query": _current_query_without(request, "page"),
        "data_error": relation_page.error,
        "action_column_count": 1 if table.primary_key_columns else 0,
    }
    context.update(
        _worksheet_context(
            detect_active_worksheet(table.name, selected_preset.slug if selected_preset else preset_slug or None)
        )
    )
    return render(request, "portal/table_detail.html", context)


@login_required
def table_row_detail(request, table_name: str):
    try:
        table = get_table_metadata(table_name)
    except SchemaMetadataError as exc:
        raise Http404(str(exc)) from exc

    key_pairs = {column_name: request.GET.get(column_name) for column_name in table.primary_key_columns}
    row, error = fetch_row_detail(table, key_pairs)

    context = {
        "table": table,
        "row": row,
        "row_items": [(column.column_name, row.get(column.column_name) if row else None) for column in table.columns],
        "data_error": error,
        "return_url": reverse("table_detail", kwargs={"table_name": table.name}),
    }
    context.update(_worksheet_context(detect_active_worksheet(table.name)))
    return render(request, "portal/table_row_detail.html", context)


@login_required
def saved_view_list(request):
    views = SavedTableView.objects.filter(user=request.user).order_by("table_name", "-is_default", "name")
    return render(
        request,
        "portal/saved_view_list.html",
        {
            "views": views,
            "joined_views": SavedJoinedView.objects.filter(user=request.user).order_by("base_table_name", "name"),
            "lab_presets": get_lab_presets(),
        },
    )


def _base_edit_url(table, raw_row: dict) -> str | None:
    if table.name == "sample":
        og_id = raw_row.get(hidden_base_pk_alias("og_id"))
        if og_id:
            return reverse("worksheet_metadata_edit", kwargs={"og_id": og_id})
    if table.name == "rna_extraction":
        rna_id = raw_row.get(hidden_base_pk_alias("rna_id"))
        if rna_id:
            return reverse("worksheet_rna_extraction_edit", kwargs={"rna_id": rna_id})
    return None


@login_required
def worksheet_metadata(request):
    page_number = _safe_page_number(request.GET.get("page"))
    query = request.GET.get("q", "").strip()
    relation_page = fetch_sample_metadata_page(search_query=query, page_number=page_number, page_size=PAGE_SIZE)
    page_obj = Paginator(range(relation_page.total_count), PAGE_SIZE).get_page(page_number)
    display_columns = [
        {
            "key": column_name,
            "label": sample_column_label(column_name),
            "editable": column_name in SAMPLE_INLINE_EDITABLE_COLUMNS,
            "field_name": column_name,
            "editor_type": SAMPLE_FIELD_DEFINITIONS_BY_NAME.get(column_name).widget
            if column_name in SAMPLE_FIELD_DEFINITIONS_BY_NAME
            else "text",
        }
        for column_name in SAMPLE_LIST_COLUMNS
    ]
    rows = [
        {
            "og_id": row.get("og_id"),
            "cells": [
                {
                    "value": row.get(column["key"]),
                    "editable": column["editable"],
                    "field_name": column["field_name"],
                    "editor_type": column["editor_type"],
                }
                for column in display_columns
            ],
        }
        for row in relation_page.rows
    ]

    context = {
        "page_obj": page_obj,
        "rows": rows,
        "query": query,
        "display_columns": display_columns,
        "data_error": relation_page.error,
        "pagination_query": _current_query_without(request, "page"),
        "unmapped_fields": WORKBOOK_UNMAPPED_METADATA_FIELDS,
    }
    context.update(_worksheet_context("metadata"))
    return render(request, "portal/worksheet_metadata_list.html", context)


@login_required
@require_POST
def worksheet_metadata_bulk_update(request):
    try:
        payload = json.loads(request.body or "{}")
        updated_count = bulk_update_sample_metadata(payload.get("rows") or [])
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True, "updated_count": updated_count})


@login_required
def worksheet_metadata_create(request):
    if request.method == "POST":
        form = SampleIntakeForm(request.POST)
        if form.is_valid():
            try:
                og_num, og_id = create_sample_metadata_record(form.cleaned_data)
            except Exception as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"Created specimen {og_id} (OG {og_num}).")
                return redirect("worksheet_metadata")
    else:
        form = SampleIntakeForm()

    context = {
        "form": form,
        "title": "New 1.MetaData row",
        "mode": "create",
        "identity_note": "OG number and Specimen ID will be generated automatically on save.",
        "unmapped_fields": WORKBOOK_UNMAPPED_METADATA_FIELDS,
    }
    context.update(_worksheet_context("metadata"))
    return render(request, "portal/worksheet_metadata_form.html", context)


@login_required
def worksheet_metadata_edit(request, og_id: str):
    row, error = fetch_sample_metadata_record(og_id)
    if error:
        raise Http404(error)

    if request.method == "POST":
        form = SampleIntakeForm(request.POST)
        if form.is_valid():
            try:
                update_sample_metadata_record(og_id, form.cleaned_data)
            except Exception as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"Updated specimen {og_id}.")
                return redirect("worksheet_metadata")
    else:
        initial_form = SampleIntakeForm()
        form = SampleIntakeForm(initial={name: row.get(name) for name in initial_form.fields})

    context = {
        "form": form,
        "title": f"Edit 1.MetaData row {og_id}",
        "mode": "edit",
        "identity_note": f"Editing OG {row.get('og_num') or '-'} / {og_id}",
        "unmapped_fields": WORKBOOK_UNMAPPED_METADATA_FIELDS,
    }
    context.update(_worksheet_context("metadata"))
    return render(request, "portal/worksheet_metadata_form.html", context)


@login_required
def worksheet_rna_extractions(request):
    page_number = _safe_page_number(request.GET.get("page"))
    query = request.GET.get("q", "").strip()
    relation_page = fetch_rna_extraction_page(search_query=query, page_number=page_number, page_size=PAGE_SIZE)
    page_obj = Paginator(range(relation_page.total_count), PAGE_SIZE).get_page(page_number)
    display_columns = [
        {
            "key": column_name.replace(".", "__"),
            "label": rna_extraction_column_label(column_name),
            "editable": column_name.startswith("rna_extraction.")
            and column_name.split(".", 1)[1] in RNA_EXTRACTION_INLINE_EDITABLE_COLUMNS,
            "field_name": column_name.split(".", 1)[1] if column_name.startswith("rna_extraction.") else "",
            "editor_type": RNA_EXTRACTION_FIELD_DEFINITIONS_BY_NAME[column_name.split(".", 1)[1]].widget
            if column_name.startswith("rna_extraction.")
            and column_name.split(".", 1)[1] in RNA_EXTRACTION_FIELD_DEFINITIONS_BY_NAME
            else "text",
        }
        for column_name in RNA_EXTRACTION_LIST_COLUMNS
    ]
    rows = [
        {
            "rna_id": row.get("rna_extraction__rna_id"),
            "cells": [
                {
                    "value": row.get(column["key"]),
                    "editable": column["editable"],
                    "field_name": column["field_name"],
                    "editor_type": column["editor_type"],
                }
                for column in display_columns
            ],
        }
        for row in relation_page.rows
    ]

    context = {
        "page_obj": page_obj,
        "rows": rows,
        "query": query,
        "display_columns": display_columns,
        "data_error": relation_page.error,
        "pagination_query": _current_query_without(request, "page"),
        "unmapped_fields": WORKBOOK_UNMAPPED_RNA_FIELDS,
    }
    context.update(_worksheet_context("rna_extractions"))
    return render(request, "portal/worksheet_rna_extraction_list.html", context)


@login_required
@require_POST
def worksheet_rna_extractions_bulk_update(request):
    try:
        payload = json.loads(request.body or "{}")
        updated_count = bulk_update_rna_extractions(payload.get("rows") or [])
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": True, "updated_count": updated_count})


@login_required
def worksheet_rna_extraction_create(request):
    linked_context = None
    if request.method == "POST":
        form = RnaExtractionForm(request.POST)
        if form.is_valid():
            try:
                rna_id, og_id = create_rna_extraction_record(form.cleaned_data)
            except Exception as exc:
                form.add_error(None, str(exc))
                try:
                    linked_context = resolve_rna_identity(
                        form.cleaned_data["tissue_id"],
                        int(form.cleaned_data["ext_num"]),
                    )
                except Exception:
                    linked_context = None
            else:
                messages.success(request, f"Created RNA extraction {rna_id} for specimen {og_id}.")
                return redirect("worksheet_rna_extractions")
    else:
        form = RnaExtractionForm(initial={"ext_num": 1})

    context = {
        "form": form,
        "title": "New 3.RNAExtractions row",
        "mode": "create",
        "identity_note": "Tube ID and Specimen ID will be derived from Tissue ID and extraction number.",
        "unmapped_fields": WORKBOOK_UNMAPPED_RNA_FIELDS,
        "linked_context": linked_context,
    }
    context.update(_worksheet_context("rna_extractions"))
    return render(request, "portal/worksheet_rna_extraction_form.html", context)


@login_required
def worksheet_rna_extraction_edit(request, rna_id: str):
    row, error = fetch_rna_extraction_record(rna_id)
    if error:
        raise Http404(error)

    linked_context = None
    try:
        linked_context = resolve_rna_identity(row.get("tissue_id"), int(row.get("ext_num") or 1))
    except Exception:
        linked_context = None

    if request.method == "POST":
        form = RnaExtractionForm(request.POST, initial=row, lock_identity=True)
        if form.is_valid():
            try:
                update_rna_extraction_record(rna_id, form.cleaned_data)
            except Exception as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, f"Updated RNA extraction {rna_id}.")
                return redirect("worksheet_rna_extractions")
    else:
        form = RnaExtractionForm(initial={name: row.get(name) for name in RnaExtractionForm().fields}, lock_identity=True)

    context = {
        "form": form,
        "title": f"Edit 3.RNAExtractions row {rna_id}",
        "mode": "edit",
        "identity_note": f"Editing tube {rna_id} for specimen {row.get('og_id') or '-'}",
        "unmapped_fields": WORKBOOK_UNMAPPED_RNA_FIELDS,
        "linked_context": linked_context,
    }
    context.update(_worksheet_context("rna_extractions"))
    return render(request, "portal/worksheet_rna_extraction_form.html", context)


@login_required
def saved_view_create(request):
    selected_table = request.POST.get("table_name") or request.GET.get("table")
    if request.method == "POST":
        form = SavedTableViewForm(request.POST)
        if form.is_valid():
            saved_view = form.save(commit=False)
            saved_view.user = request.user
            saved_view.save()
            messages.success(request, "Saved table view created.")
            return redirect(f"{reverse('table_detail', kwargs={'table_name': saved_view.table_name})}?view={saved_view.pk}")
    else:
        form = SavedTableViewForm(initial={"table_name": selected_table} if selected_table else None)

    return render(
        request,
        "portal/saved_view_form.html",
        {"form": form, "title": "New Saved View"},
    )


@login_required
def joined_view_detail(request, pk: int):
    saved_view = get_object_or_404(SavedJoinedView, pk=pk, user=request.user)
    base_table = get_table_metadata(saved_view.base_table_name)
    page_number = _safe_page_number(request.GET.get("page"))
    query = request.GET.get("q", "").strip()
    relation_page = fetch_joined_view_page(
        base_table_name=saved_view.base_table_name,
        visible_columns=saved_view.visible_columns,
        search_query=query,
        ordering=saved_view.ordering,
        page_number=page_number,
        page_size=PAGE_SIZE,
    )
    page_obj = Paginator(range(relation_page.total_count), PAGE_SIZE).get_page(page_number)
    display_columns = joined_view_display_columns(saved_view.base_table_name, saved_view.visible_columns)

    rows = []
    for raw_row in relation_page.rows:
        base_key_values = {
            column_name: raw_row.get(hidden_base_pk_alias(column_name))
            for column_name in base_table.primary_key_columns
        }
        rows.append(
            {
                "cells": [raw_row.get(column["key"]) for column in display_columns],
                "detail_url": build_row_detail_url(base_table, base_key_values) if base_table.primary_key_columns else None,
                "edit_url": _base_edit_url(base_table, raw_row),
            }
        )

    context = {
        "saved_view": saved_view,
        "base_table": base_table,
        "display_columns": display_columns,
        "rows": rows,
        "query": query,
        "page_obj": page_obj,
        "pagination_query": _current_query_without(request, "page"),
        "data_error": relation_page.error,
        "action_column_count": 1 if base_table.primary_key_columns else 0,
    }
    context.update(_worksheet_context(detect_active_worksheet(saved_view.base_table_name)))
    return render(request, "portal/joined_view_detail.html", context)


@login_required
def joined_view_create(request):
    selected_base_table = request.POST.get("base_table_name") or request.GET.get("base_table")
    if request.method == "POST":
        form = SavedJoinedViewForm(request.POST)
        if form.is_valid():
            saved_view = form.save(commit=False)
            saved_view.user = request.user
            saved_view.save()
            messages.success(request, "Joined view created.")
            return redirect("joined_view_detail", pk=saved_view.pk)
    else:
        form = SavedJoinedViewForm(initial={"base_table_name": selected_base_table} if selected_base_table else None)

    return render(
        request,
        "portal/joined_view_form.html",
        {"form": form, "title": "New Joined View"},
    )


@login_required
def joined_view_edit(request, pk: int):
    saved_view = get_object_or_404(SavedJoinedView, pk=pk, user=request.user)

    if request.method == "POST":
        form = SavedJoinedViewForm(request.POST, instance=saved_view)
        if form.is_valid():
            saved_view = form.save()
            messages.success(request, "Joined view updated.")
            return redirect("joined_view_detail", pk=saved_view.pk)
    else:
        form = SavedJoinedViewForm(instance=saved_view)

    return render(
        request,
        "portal/joined_view_form.html",
        {"form": form, "title": f"Edit {saved_view.name}"},
    )


@login_required
def joined_view_delete(request, pk: int):
    saved_view = get_object_or_404(SavedJoinedView, pk=pk, user=request.user)

    if request.method == "POST":
        saved_view.delete()
        messages.success(request, "Joined view deleted.")
        return redirect("saved_view_list")

    return render(request, "portal/joined_view_confirm_delete.html", {"saved_view": saved_view})


@login_required
def saved_view_edit(request, pk):
    saved_view = get_object_or_404(SavedTableView, pk=pk, user=request.user)

    if request.method == "POST":
        form = SavedTableViewForm(request.POST, instance=saved_view)
        if form.is_valid():
            saved_view = form.save()
            messages.success(request, "Saved table view updated.")
            return redirect(f"{reverse('table_detail', kwargs={'table_name': saved_view.table_name})}?view={saved_view.pk}")
    else:
        form = SavedTableViewForm(instance=saved_view)

    return render(
        request,
        "portal/saved_view_form.html",
        {"form": form, "title": f"Edit {saved_view.name}"},
    )


@login_required
def saved_view_delete(request, pk):
    saved_view = get_object_or_404(SavedTableView, pk=pk, user=request.user)

    if request.method == "POST":
        table_name = saved_view.table_name
        saved_view.delete()
        messages.success(request, "Saved table view deleted.")
        return redirect("table_detail", table_name=table_name)

    return render(request, "portal/saved_view_confirm_delete.html", {"saved_view": saved_view})
