from django import forms

from fournisseurs.models import Fournisseur


class FournisseurForm(forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = ['nom', 'contact', 'statut']
        widgets = {
            'nom': forms.TextInput(
                attrs={
                    'class': 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:border-black focus:outline-none',
                    'placeholder': 'Nom du fournisseur',
                }
            ),
            'contact': forms.TextInput(
                attrs={
                    'class': 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:border-black focus:outline-none',
                    'placeholder': 'Téléphone / Email / Personne de contact',
                }
            ),
            'statut': forms.Select(
                attrs={
                    'class': 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:border-black focus:outline-none'
                }
            ),
        }

