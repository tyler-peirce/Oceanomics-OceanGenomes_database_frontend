from django import forms

from .joined_views import (
    default_joined_ordering,
    default_joined_visible_columns,
    joined_view_column_choices,
    joined_view_ordering_choices,
)
from .models import SavedJoinedView, SavedTableView
from .rna_extractions import RNA_EXTRACTION_FIELD_DEFINITIONS, rna_extraction_field_groups
from .sample_metadata import SAMPLE_FIELD_DEFINITIONS, sample_field_groups
from .schema import get_schema_catalog, get_table_metadata


class DateInput(forms.DateInput):
    input_type = "date"


class SampleIntakeForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for definition in SAMPLE_FIELD_DEFINITIONS:
            if definition.widget == "date":
                field = forms.DateField(required=definition.required, label=definition.label, widget=DateInput())
            elif definition.widget == "textarea":
                field = forms.CharField(
                    required=definition.required,
                    label=definition.label,
                    widget=forms.Textarea(attrs={"rows": 4}),
                )
            else:
                field = forms.CharField(required=definition.required, label=definition.label)

            if definition.help_text:
                field.help_text = definition.help_text

            self.fields[definition.name] = field

        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-input").strip()

        self.fieldsets = [
            {
                "legend": group["legend"],
                "fields": [self[field.name] for field in group["fields"]],
            }
            for group in sample_field_groups()
        ]


class RnaExtractionForm(forms.Form):
    def __init__(self, *args, lock_identity: bool = False, **kwargs):
        super().__init__(*args, **kwargs)

        for definition in RNA_EXTRACTION_FIELD_DEFINITIONS:
            if definition.widget == "date":
                field = forms.DateField(required=definition.required, label=definition.label, widget=DateInput())
            elif definition.widget == "integer":
                field = forms.IntegerField(required=definition.required, label=definition.label, min_value=1)
            elif definition.widget == "float":
                field = forms.FloatField(required=definition.required, label=definition.label)
            elif definition.widget == "textarea":
                field = forms.CharField(
                    required=definition.required,
                    label=definition.label,
                    widget=forms.Textarea(attrs={"rows": 4}),
                )
            else:
                field = forms.CharField(required=definition.required, label=definition.label)

            if definition.help_text:
                field.help_text = definition.help_text

            if lock_identity and definition.name in {"tissue_id", "ext_num"}:
                field.disabled = True

            self.fields[definition.name] = field

        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-input").strip()

        self.fieldsets = [
            {
                "legend": group["legend"],
                "fields": [self[field.name] for field in group["fields"]],
            }
            for group in rna_extraction_field_groups()
        ]


class SavedTableViewForm(forms.ModelForm):
    table_name = forms.ChoiceField(required=True)
    visible_columns = forms.MultipleChoiceField(
        choices=(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    ordering = forms.ChoiceField(required=False, choices=())

    class Meta:
        model = SavedTableView
        fields = ["name", "table_name", "visible_columns", "ordering", "is_default"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        catalog = get_schema_catalog()
        table_choices = [
            (table.name, f"{table.name} ({table.column_count} columns, {table.relation_kind})")
            for table in catalog
        ]
        self.fields["table_name"].choices = table_choices

        selected_table_name = (
            self.data.get("table_name")
            or self.initial.get("table_name")
            or getattr(self.instance, "table_name", "")
            or (catalog[0].name if catalog else "")
        )

        if selected_table_name:
            table = get_table_metadata(selected_table_name)
            column_choices = []
            for column in table.columns:
                label_parts = [column.column_name, column.data_type]
                if column.is_primary_key:
                    label_parts.append("PK")
                elif column.is_in_unique_constraint:
                    label_parts.append("unique")
                if not column.is_nullable:
                    label_parts.append("required")
                column_choices.append((column.column_name, " | ".join(label_parts)))

            ordering_choices = [("", "Natural order")]
            for column_name in table.ordered_column_names:
                ordering_choices.append((column_name, f"{column_name} (ascending)"))
                ordering_choices.append((f"-{column_name}", f"{column_name} (descending)"))

            self.fields["visible_columns"].choices = column_choices
            self.fields["ordering"].choices = ordering_choices

            if not self.is_bound:
                self.initial.setdefault("table_name", selected_table_name)
                self.initial.setdefault("visible_columns", table.default_visible_columns)
                self.initial.setdefault("ordering", table.default_ordering)

        for name, field in self.fields.items():
            if name == "visible_columns":
                continue
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-input").strip()

        self.fields["table_name"].widget.attrs["onchange"] = (
            "window.location='?table=' + encodeURIComponent(this.value)"
        )

    def clean_visible_columns(self):
        return list(self.cleaned_data["visible_columns"])

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.visible_columns = self.cleaned_data["visible_columns"]
        if commit:
            instance.save()
        return instance


class SavedJoinedViewForm(forms.ModelForm):
    base_table_name = forms.ChoiceField(required=True, label="Base table")
    visible_columns = forms.MultipleChoiceField(
        choices=(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    ordering = forms.ChoiceField(required=False, choices=())

    class Meta:
        model = SavedJoinedView
        fields = ["name", "base_table_name", "visible_columns", "ordering"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        catalog = get_schema_catalog()
        table_choices = [
            (table.name, f"{table.name} ({table.column_count} columns, {table.relation_kind})")
            for table in catalog
        ]
        self.fields["base_table_name"].choices = table_choices

        selected_base_table = (
            self.data.get("base_table_name")
            or self.initial.get("base_table_name")
            or getattr(self.instance, "base_table_name", "")
            or (catalog[0].name if catalog else "")
        )

        if selected_base_table:
            self.fields["visible_columns"].choices = joined_view_column_choices(selected_base_table)
            self.fields["ordering"].choices = joined_view_ordering_choices(selected_base_table)

            if not self.is_bound:
                self.initial.setdefault("base_table_name", selected_base_table)
                self.initial.setdefault("visible_columns", default_joined_visible_columns(selected_base_table))
                self.initial.setdefault("ordering", default_joined_ordering(selected_base_table))

        for name, field in self.fields.items():
            if name == "visible_columns":
                continue
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-input").strip()

        self.fields["base_table_name"].widget.attrs["onchange"] = (
            "window.location='?base_table=' + encodeURIComponent(this.value)"
        )

    def clean_visible_columns(self):
        return list(self.cleaned_data["visible_columns"])

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.visible_columns = self.cleaned_data["visible_columns"]
        if commit:
            instance.save()
        return instance
