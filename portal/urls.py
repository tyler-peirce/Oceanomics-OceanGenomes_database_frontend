from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("records/", views.record_list, name="record_list"),
    path("records/new/", views.record_create, name="record_create"),
    path("records/<int:pk>/edit/", views.record_edit, name="record_edit"),
    path("views/", views.saved_view_list, name="saved_view_list"),
    path("views/new/", views.saved_view_create, name="saved_view_create"),
    path("views/<int:pk>/edit/", views.saved_view_edit, name="saved_view_edit"),
    path("views/<int:pk>/delete/", views.saved_view_delete, name="saved_view_delete"),
]
