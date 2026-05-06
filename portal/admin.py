from django.contrib import admin

from .models import SavedJoinedView, SavedTableView


@admin.register(SavedTableView)
class SavedTableViewAdmin(admin.ModelAdmin):
    list_display = ("name", "table_name", "user", "is_default", "ordering")
    list_filter = ("table_name", "is_default")
    search_fields = ("name", "table_name", "user__username")


@admin.register(SavedJoinedView)
class SavedJoinedViewAdmin(admin.ModelAdmin):
    list_display = ("name", "base_table_name", "user", "ordering")
    list_filter = ("base_table_name",)
    search_fields = ("name", "base_table_name", "user__username")
