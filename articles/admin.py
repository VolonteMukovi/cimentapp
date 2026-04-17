from django.contrib import admin

from articles.models import Article, SousTypeArticle, TypeArticle, Unite


@admin.register(TypeArticle)
class TypeArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'libelle', 'ordre', 'actif')
    list_filter = ('actif',)
    search_fields = ('code', 'libelle')


@admin.register(SousTypeArticle)
class SousTypeArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'type_article_id', 'code', 'libelle', 'ordre', 'actif')
    list_filter = ('actif', 'type_article_id')
    search_fields = ('code', 'libelle')


@admin.register(Unite)
class UniteAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'libelle', 'actif')
    list_filter = ('actif',)
    search_fields = ('code', 'libelle')


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        'article_id',
        'nom',
        'sous_type_article_id',
        'unite_id',
        'entreprise_id',
        'date_modification',
    )
    list_filter = ('entreprise_id',)
    search_fields = ('article_id', 'nom')
    readonly_fields = ('article_id', 'date_creation', 'date_modification')
