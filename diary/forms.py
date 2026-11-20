from django import forms

from .models import DiaryEntry


class DiaryForm(forms.ModelForm):
    class Meta:
        model = DiaryEntry
        fields = ["date", "kind", "material", "quantity", "payment_type", "amount", "paid_to", "note", "photo"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 2}),
            "quantity": forms.NumberInput(attrs={"inputmode": "decimal", "step": "any"}),
            "amount": forms.NumberInput(attrs={"inputmode": "numeric"}),
            "photo": forms.ClearableFileInput(attrs={"accept": "image/*", "capture": "environment"}),
        }

    def __init__(self, *args, ui_lang="en", **kwargs):
        from core.i18n import tr

        super().__init__(*args, **kwargs)
        for name in ("kind", "material", "payment_type"):
            f = self.fields[name]
            f.choices = [(v, tr(str(label), ui_lang) if v else label) for v, label in f.choices]

    def clean(self):
        d = super().clean()
        kind = d.get("kind")
        if kind == DiaryEntry.MATERIAL and (not d.get("material") or d.get("quantity") in (None, "")):
            raise forms.ValidationError("For material received, choose the material and type the quantity.")
        if kind == DiaryEntry.PAYMENT and (not d.get("amount") or not d.get("payment_type")):
            raise forms.ValidationError("For a payment, choose the type and type the amount.")
        if kind == DiaryEntry.NOTE and not d.get("note"):
            raise forms.ValidationError("Write the note.")
        if kind == DiaryEntry.PHOTO and not d.get("photo"):
            raise forms.ValidationError("Add the photo.")
        return d
