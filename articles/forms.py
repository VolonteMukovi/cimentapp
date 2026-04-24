"""Formulaires articles (sélections métier → enregistrement d’IDs int)."""

from __future__ import annotations

from django import forms

from articles.models import Article, SousTypeArticle, TypeArticle, Unite


class UniteForm(forms.ModelForm):
    class Meta:
        model = Unite
        fields = ('code', 'libelle', 'actif')
        widgets = {
            'code': forms.TextInput(attrs={'class': 'art-input', 'maxlength': '32', 'autocomplete': 'off'}),
            'libelle': forms.TextInput(attrs={'class': 'art-input', 'maxlength': '128', 'autocomplete': 'off'}),
        }


class TypeArticleForm(forms.ModelForm):
    class Meta:
        model = TypeArticle
        fields = ('libelle', 'description')
        widgets = {
            'libelle': forms.TextInput(attrs={'class': 'art-input', 'maxlength': '255', 'autocomplete': 'off'}),
            'description': forms.Textarea(attrs={'class': 'art-input', 'rows': 3}),
        }


class ArticleForm(forms.ModelForm):
    """
    Champs modèle hors images (gérées en vue : upload + JSON).
    POST : <prefix>image_files (multiple), <prefix>main_image_index (champ caché),
    <prefix>existing_images_json (édition).
    """

    class Meta:
        model = Article
        fields = ('nom',)
        widgets = {
            'nom': forms.TextInput(
                attrs={
                    'class': 'art-input',
                    'autocomplete': 'off',
                    'maxlength': '500',
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        types = {t.id: t.libelle for t in TypeArticle.objects.all().order_by('libelle')}
        st_qs = SousTypeArticle.objects.all().order_by('type_article_id', 'libelle')
        self.fields['sous_type_article_id'] = forms.ChoiceField(
            label='Sous-type',
            choices=[('', '— Choisir un sous-type —')]
            + [(str(st.id), f"{st.libelle} ({types.get(st.type_article_id, '—')})") for st in st_qs],
            required=True,
            widget=forms.Select(attrs={'class': 'art-input'}),
        )
        u_qs = Unite.objects.filter(actif=True).order_by('libelle')
        self.fields['unite_id'] = forms.ChoiceField(
            label='Unité',
            choices=[('', '— Choisir une unité —')] + [(str(u.id), f'{u.libelle} ({u.code})') for u in u_qs],
            required=True,
            widget=forms.Select(attrs={'class': 'art-input'}),
        )

        inst = kwargs.get('instance')
        if inst is not None:
            self.fields['sous_type_article_id'].initial = str(inst.sous_type_article_id)
            self.fields['unite_id'].initial = str(inst.unite_id)

    def clean_sous_type_article_id(self):
        v = self.cleaned_data.get('sous_type_article_id')
        if not v:
            raise forms.ValidationError('Choisissez un sous-type.')
        pk = int(v)
        if not SousTypeArticle.objects.filter(pk=pk).exists():
            raise forms.ValidationError('Sous-type invalide.')
        return pk

    def clean_unite_id(self):
        v = self.cleaned_data.get('unite_id')
        if not v:
            raise forms.ValidationError('Choisissez une unité.')
        pk = int(v)
        if not Unite.objects.filter(pk=pk, actif=True).exists():
            raise forms.ValidationError('Unité invalide.')
        return pk

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.sous_type_article_id = self.cleaned_data['sous_type_article_id']
        instance.unite_id = self.cleaned_data['unite_id']
        if commit:
            instance.save()
        return instance


class SousTypeArticleForm(forms.ModelForm):
    """Champ métier `type_article` (select) → `instance.type_article_id` à l’enregistrement.
    Évite le conflit ModelForm / champ modèle homonyme `type_article_id`."""

    type_article = forms.ChoiceField(
        label='Type',
        required=True,
        widget=forms.Select(attrs={'class': 'art-input'}),
    )

    class Meta:
        model = SousTypeArticle
        fields = ('libelle', 'description')
        widgets = {
            'libelle': forms.TextInput(attrs={'class': 'art-input', 'maxlength': '255', 'autocomplete': 'off'}),
            'description': forms.Textarea(attrs={'class': 'art-input', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        t_qs = TypeArticle.objects.all().order_by('libelle')
        self.fields['type_article'].choices = [('', '— Choisir un type —')] + [
            (str(t.id), t.libelle) for t in t_qs
        ]
        inst = kwargs.get('instance')
        if inst is not None:
            self.fields['type_article'].initial = str(inst.type_article_id)

    def clean_type_article(self):
        v = self.cleaned_data.get('type_article')
        if not v:
            raise forms.ValidationError('Choisissez un type.')
        pk = int(v)
        if not TypeArticle.objects.filter(pk=pk).exists():
            raise forms.ValidationError('Type invalide.')
        return pk

    def save(self, commit=True):
        inst = super().save(commit=False)
        inst.type_article_id = int(self.cleaned_data['type_article'])
        if commit:
            inst.save()
        return inst
