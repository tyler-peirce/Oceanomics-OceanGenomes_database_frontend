from django import forms

from .models import LabRecord, SavedView


class DateInput(forms.DateInput):
    input_type = "date"


class LabRecordForm(forms.ModelForm):
    class Meta:
        model = LabRecord
        fields = [
            "sample_code",
            "submitter",
            "project",
            "received_at",
            "processed_at",
            "status",
            "qc_score",
            "read_count",
            "notes",
        ]
        widgets = {
            "received_at": DateInput(),
            "processed_at": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-input").strip()


class SavedViewForm(forms.ModelForm):
    visible_columns = forms.MultipleChoiceField(
        choices=SavedView.COLUMN_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    class Meta:
        model = SavedView
        fields = ["name", "visible_columns", "status_filter", "min_qc_score", "ordering", "is_default"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields["visible_columns"].initial = self.instance.visible_columns

        for name, field in self.fields.items():
            if name == "visible_columns":
                continue
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-input").strip()

    def clean_visible_columns(self):
        return list(self.cleaned_data["visible_columns"])

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.visible_columns = self.cleaned_data["visible_columns"]
        if commit:
            instance.save()
        return instance
