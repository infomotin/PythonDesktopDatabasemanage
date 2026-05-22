from django import forms
from apps.query_builder.models import SavedQuery


class SavedQueryForm(forms.ModelForm):
    class Meta:
        model = SavedQuery
        fields = ["name", "description", "raw_sql", "tag", "visibility", "category", "purpose"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "w-full rounded border border-gray-700 bg-gray-900 text-white px-3 py-2"}),
            "description": forms.Textarea(attrs={"class": "w-full rounded border border-gray-700 bg-gray-900 text-white px-3 py-2", "rows": 3}),
            "raw_sql": forms.Textarea(attrs={"class": "w-full rounded border border-gray-700 bg-gray-900 text-white px-3 py-2 font-mono", "rows": 6}),
            "tag": forms.TextInput(attrs={"class": "w-full rounded border border-gray-700 bg-gray-900 text-white px-3 py-2"}),
            "category": forms.TextInput(attrs={"class": "w-full rounded border border-gray-700 bg-gray-900 text-white px-3 py-2"}),
            "purpose": forms.TextInput(attrs={"class": "w-full rounded border border-gray-700 bg-gray-900 text-white px-3 py-2"}),
            "visibility": forms.Select(attrs={"class": "w-full rounded border border-gray-700 bg-gray-900 text-white px-3 py-2"}),
        }
