"""Vues CRUD articles (accès magasin, filtrage entreprise session)."""

from __future__ import annotations

import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.utils import timezone
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, ListView

from articles.forms import ArticleForm
from articles.models import Article, SousTypeArticle, Unite
from articles.utils import build_images_from_post, delete_article_media
from users.constants import SESSION_ACTIVE_ENTREPRISE_ID
from users.models import User
from users.navigation import can_access_store_module


class ArticleStoreAccessMixin(LoginRequiredMixin):
    """Connexion staff + droit module articles."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not isinstance(request.user, User):
            return self.handle_no_permission()
        if not can_access_store_module(request.user, 'articles'):
            messages.error(request, 'Accès non autorisé pour votre rôle.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class ArticleQuerysetMixin:
    """Articles visibles selon entreprise active (superadmin sans session : tout)."""

    def scoped_articles(self):
        qs = Article.objects.all()
        eid = self.request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
        user = self.request.user
        if isinstance(user, User) and user.is_superadmin_role() and eid is None:
            return qs
        if eid is not None:
            return qs.filter(entreprise_id=int(eid))
        return Article.objects.none()

    def resolve_entreprise_id_for_write(self) -> int | None:
        eid = self.request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
        if eid is not None:
            return int(eid)
        user = self.request.user
        if isinstance(user, User) and user.is_superadmin_role():
            return None
        return None


class ArticleListView(ArticleStoreAccessMixin, ArticleQuerysetMixin, ListView):
    model = Article
    template_name = 'articles/article_list.html'
    context_object_name = 'articles'
    paginate_by = 15

    def get_base_queryset(self):
        qs = self.scoped_articles()
        q = (self.request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(nom__icontains=q)
                | Q(article_id__icontains=q),
            )
        st = self.request.GET.get('sous_type')
        if st and st.isdigit():
            qs = qs.filter(sous_type_article_id=int(st))
        uid = self.request.GET.get('unite')
        if uid and uid.isdigit():
            qs = qs.filter(unite_id=int(uid))
        ent = self.request.GET.get('entreprise')
        if ent and ent.isdigit() and isinstance(self.request.user, User) and self.request.user.is_superadmin_role():
            qs = qs.filter(entreprise_id=int(ent))

        sort_key = (self.request.GET.get('sort') or 'nom').strip()
        if sort_key == 'recent':
            qs = qs.order_by('-date_creation', 'nom')
        elif sort_key == 'oldest':
            qs = qs.order_by('date_creation', 'nom')
        elif sort_key == 'nom_desc':
            qs = qs.order_by('-nom')
        else:
            qs = qs.order_by('nom')
        return qs

    def stats_for_scope(self) -> dict:
        """Indicateurs sur le périmètre entreprise (sans filtres de recherche)."""
        base = self.scoped_articles()
        total = base.count()
        with_images = base.filter(images__0__isnull=False).count()
        since = timezone.now() - timedelta(days=7)
        recent = base.filter(date_creation__gte=since).count()
        return {
            'total': total,
            'with_images': with_images,
            'recent': recent,
            'without_images': max(0, total - with_images),
        }

    def get_queryset(self):
        return self.get_base_queryset()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_create'] = ArticleForm(prefix='create')
        ctx['form_edit'] = ArticleForm(prefix='edit')
        ctx['MEDIA_URL'] = settings.MEDIA_URL
        ctx['search_q'] = (self.request.GET.get('q') or '').strip()
        ctx['filter_sous_type'] = self.request.GET.get('sous_type') or ''
        ctx['filter_unite'] = self.request.GET.get('unite') or ''
        ctx['filter_entreprise'] = self.request.GET.get('entreprise') or ''
        ctx['filter_sort'] = (self.request.GET.get('sort') or 'nom').strip()
        ctx['stats'] = self.stats_for_scope()
        qcopy = self.request.GET.copy()
        if 'page' in qcopy:
            del qcopy['page']
        qs = qcopy.urlencode()
        ctx['pagination_prefix'] = ('?' + qs + '&') if qs else '?'
        ctx['sous_types'] = SousTypeArticle.objects.filter(actif=True).order_by('type_article_id', 'libelle')
        ctx['unites'] = Unite.objects.filter(actif=True).order_by('libelle')
        ctx['total_filtered'] = self.get_base_queryset().count()
        page_items = list(ctx.get('articles') or [])
        ids_st = {a.sous_type_article_id for a in page_items}
        ids_u = {a.unite_id for a in page_items}
        st_map = {x.id: x.libelle for x in SousTypeArticle.objects.filter(id__in=ids_st)} if ids_st else {}
        u_map = {x.id: f'{x.libelle} ({x.code})' for x in Unite.objects.filter(id__in=ids_u)} if ids_u else {}
        ctx['article_rows'] = [
            {
                'article': a,
                'sous_type_libelle': st_map.get(a.sous_type_article_id, '—'),
                'unite_libelle': u_map.get(a.unite_id, '—'),
            }
            for a in page_items
        ]
        mu = settings.MEDIA_URL
        if not str(mu).endswith('/'):
            mu = f'{mu}/'
        galleries: dict[str, list[dict]] = {}
        for a in page_items:
            slides: list[dict] = []
            if isinstance(a.images, list):
                for im in a.images:
                    if isinstance(im, dict) and im.get('image'):
                        path = str(im['image']).lstrip('/')
                        slides.append(
                            {
                                'src': f'{mu}{path}',
                                'alt': a.nom,
                                'main': bool(im.get('is_main')),
                            },
                        )
            galleries[a.article_id] = slides
        ctx['article_galleries_json'] = json.dumps(galleries)
        return ctx


class ArticleCreateView(ArticleStoreAccessMixin, ArticleQuerysetMixin, FormView):
    form_class = ArticleForm
    http_method_names = ['post']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['prefix'] = 'create'
        return kwargs

    def form_valid(self, form):
        eid = self.resolve_entreprise_id_for_write()
        if eid is None:
            messages.error(
                self.request,
                'Sélectionnez une entreprise active pour créer un article.',
            )
            return redirect('store_articles')
        obj = form.save(commit=False)
        obj.article_id = Article.generate_article_id()
        obj.entreprise_id = eid
        obj.images = build_images_from_post(
            self.request,
            form_prefix='create-',
            entreprise_id=eid,
            article_id=obj.article_id,
        )
        obj.save()
        messages.success(self.request, f'Article « {obj} » créé.')
        return redirect('store_articles')

    def form_invalid(self, form):
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(self.request, f'{field}: {err}')
        return redirect('store_articles')


class ArticleUpdateView(ArticleStoreAccessMixin, ArticleQuerysetMixin, FormView):
    form_class = ArticleForm
    http_method_names = ['post']

    def dispatch(self, request, *args, **kwargs):
        self.article = self.scoped_articles().filter(pk=kwargs['article_id']).first()
        if not self.article:
            raise Http404('Article introuvable.')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['prefix'] = 'edit'
        kwargs['instance'] = self.article
        return kwargs

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.images = build_images_from_post(
            self.request,
            form_prefix='edit-',
            entreprise_id=obj.entreprise_id,
            article_id=obj.article_id,
        )
        obj.save()
        messages.success(self.request, f'Article « {obj} » mis à jour.')
        return redirect('store_articles')

    def form_invalid(self, form):
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(self.request, f'{field}: {err}')
        return redirect('store_articles')


class ArticleDeleteView(ArticleStoreAccessMixin, ArticleQuerysetMixin, View):
    http_method_names = ['post']

    def post(self, request, article_id):
        obj = self.scoped_articles().filter(pk=article_id).first()
        if not obj:
            raise Http404()
        eid, aid = obj.entreprise_id, obj.article_id
        obj.delete()
        delete_article_media(eid, aid)
        messages.success(request, 'Article supprimé.')
        return redirect('store_articles')


class ArticleJsonDetailView(ArticleStoreAccessMixin, ArticleQuerysetMixin, View):
    """Données JSON pour préremplir le modal d’édition."""

    http_method_names = ['get']

    def get(self, request, article_id, *args, **kwargs):
        art = self.scoped_articles().filter(pk=article_id).first()
        if not art:
            return JsonResponse({'ok': False, 'error': 'Introuvable'}, status=404)
        st = SousTypeArticle.objects.filter(pk=art.sous_type_article_id).first()
        u = Unite.objects.filter(pk=art.unite_id).first()
        images = art.images if isinstance(art.images, list) else []
        return JsonResponse(
            {
                'ok': True,
                'article': {
                    'article_id': art.article_id,
                    'nom': art.nom,
                    'sous_type_article_id': art.sous_type_article_id,
                    'unite_id': art.unite_id,
                    'images': images,
                    'entreprise_id': art.entreprise_id,
                    'sous_type_libelle': st.libelle if st else '',
                    'unite_libelle': f'{u.libelle} ({u.code})' if u else '',
                },
            },
        )
