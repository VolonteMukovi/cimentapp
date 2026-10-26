"""Formulaires articles (sélections métier → enregistrement d’IDs int)."""

from __future__ import annotations

from django import forms

from articles.models import Article, Devise, SousTypeArticle, TypeArticle, Unite


class UniteForm(forms.ModelForm):
    class Meta:
        model = Unite
        fields = ('code', 'libelle', 'actif')
        widgets = {
            'code': forms.TextInput(attrs={'class': 'art-input', 'maxlength': '32', 'autocomplete': 'off'}),
            'libelle': forms.TextInput(attrs={'class': 'art-input', 'maxlength': '128', 'autocomplete': 'off'}),
        }

    def __init__(self, *args, entreprise_id=None, **kwargs):
        self.entreprise_id = entreprise_id
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip()
        if self.entreprise_id is None:
            raise forms.ValidationError('Sélectionnez une entreprise active.')
        duplicates = Unite.objects.filter(entreprise_id=self.entreprise_id, code=code)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError('Ce code d’unité existe déjà pour cette entreprise.')
        return code


class DeviseForm(forms.ModelForm):
    class Meta:
        model = Devise
        fields = ('code', 'libelle', 'taux_vers_principale', 'principale', 'actif')
        widgets = {
            'code': forms.TextInput(attrs={'class': 'art-input', 'maxlength': '10', 'autocomplete': 'off'}),
            'libelle': forms.TextInput(attrs={'class': 'art-input', 'maxlength': '64', 'autocomplete': 'off'}),
            'taux_vers_principale': forms.NumberInput(
                attrs={'class': 'art-input', 'min': '0.000001', 'step': '0.000001'},
            ),
        }

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            raise forms.ValidationError('Le code devise est requis.')
        return code[:10]

    def clean_taux_vers_principale(self):
        taux = self.cleaned_data.get('taux_vers_principale')
        if taux is None or taux <= 0:
            raise forms.ValidationError('Le taux doit etre superieur a 0.')
        return taux


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

    def __init__(self, *args, entreprise_id=None, include_all_settings=False, **kwargs):
        self.entreprise_id = entreprise_id
        super().__init__(*args, **kwargs)
        if entreprise_id is not None:
            types_qs = TypeArticle.objects.filter(entreprise_id=entreprise_id)
            st_qs = SousTypeArticle.objects.filter(entreprise_id=entreprise_id).order_by('type_article_id', 'libelle')
            u_qs = Unite.objects.filter(entreprise_id=entreprise_id, actif=True).order_by('libelle')
        elif include_all_settings:
            types_qs = TypeArticle.objects.exclude(entreprise_id__isnull=True)
            st_qs = SousTypeArticle.objects.exclude(entreprise_id__isnull=True).order_by('entreprise_id', 'type_article_id', 'libelle')
            u_qs = Unite.objects.filter(entreprise_id__isnull=False, actif=True).order_by('libelle')
        else:
            types_qs = TypeArticle.objects.none()
            st_qs = SousTypeArticle.objects.none()
            u_qs = Unite.objects.none()
        types = {t.id: t.libelle for t in types_qs.order_by('libelle')}
        self.fields['sous_type_article_id'] = forms.ChoiceField(
            label='Sous-type',
            choices=[('', '— Choisir un sous-type —')]
            + [(str(st.id), f"{st.libelle} ({types.get(st.type_article_id, '—')})") for st in st_qs],
            required=True,
            widget=forms.Select(attrs={'class': 'art-input'}),
        )
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
        if not SousTypeArticle.objects.filter(pk=pk, entreprise_id=self.entreprise_id).exists():
            raise forms.ValidationError('Sous-type invalide.')
        return pk

    def clean_unite_id(self):
        v = self.cleaned_data.get('unite_id')
        if not v:
            raise forms.ValidationError('Choisissez une unité.')
        pk = int(v)
        if not Unite.objects.filter(pk=pk, entreprise_id=self.entreprise_id, actif=True).exists():
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

    def __init__(self, *args, entreprise_id=None, **kwargs):
        self.entreprise_id = entreprise_id
        super().__init__(*args, **kwargs)
        t_qs = TypeArticle.objects.filter(entreprise_id=entreprise_id).order_by('libelle') if entreprise_id is not None else TypeArticle.objects.none()
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
        if not TypeArticle.objects.filter(pk=pk, entreprise_id=self.entreprise_id).exists():
            raise forms.ValidationError('Type invalide.')
        return pk

    def save(self, commit=True):
        inst = super().save(commit=False)
        inst.type_article_id = int(self.cleaned_data['type_article'])
        inst.entreprise_id = self.entreprise_id
        if commit:
            inst.save()
        return inst
