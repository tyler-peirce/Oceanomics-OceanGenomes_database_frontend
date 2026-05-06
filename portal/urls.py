from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("records/", views.table_list, name="record_list"),
    path("tables/", views.table_list, name="table_list"),
    path("tables/<str:table_name>/", views.table_detail, name="table_detail"),
    path("tables/<str:table_name>/row/", views.table_row_detail, name="table_row_detail"),
    path("worksheets/metadata/", views.worksheet_metadata, name="worksheet_metadata"),
    path("worksheets/metadata/bulk-update/", views.worksheet_metadata_bulk_update, name="worksheet_metadata_bulk_update"),
    path("worksheets/metadata/new/", views.worksheet_metadata_create, name="worksheet_metadata_create"),
    path("worksheets/metadata/<str:og_id>/edit/", views.worksheet_metadata_edit, name="worksheet_metadata_edit"),
    path("worksheets/rna-extractions/", views.worksheet_rna_extractions, name="worksheet_rna_extractions"),
    path(
        "worksheets/rna-extractions/bulk-update/",
        views.worksheet_rna_extractions_bulk_update,
        name="worksheet_rna_extractions_bulk_update",
    ),
    path("worksheets/rna-extractions/new/", views.worksheet_rna_extraction_create, name="worksheet_rna_extraction_create"),
    path(
        "worksheets/rna-extractions/<str:rna_id>/edit/",
        views.worksheet_rna_extraction_edit,
        name="worksheet_rna_extraction_edit",
    ),
    path("joined-views/new/", views.joined_view_create, name="joined_view_create"),
    path("joined-views/<int:pk>/", views.joined_view_detail, name="joined_view_detail"),
    path("joined-views/<int:pk>/edit/", views.joined_view_edit, name="joined_view_edit"),
    path("joined-views/<int:pk>/delete/", views.joined_view_delete, name="joined_view_delete"),
    path("views/", views.saved_view_list, name="saved_view_list"),
    path("views/new/", views.saved_view_create, name="saved_view_create"),
    path("views/<int:pk>/edit/", views.saved_view_edit, name="saved_view_edit"),
    path("views/<int:pk>/delete/", views.saved_view_delete, name="saved_view_delete"),
]
