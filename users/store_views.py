"""Écrans placeholder des modules magasin (articles, lots, caisse, etc.)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView

from users.models import User
from users.navigation import STORE_MODULE_LABELS, can_access_store_module


class StorePlaceholderView(LoginRequiredMixin, TemplateView):
    template_name = 'users/pages/store_module_placeholder.html'
    module_key: str = ''

    def dispatch(self, request, *args, **kwargs):
        mk = self.module_key or kwargs.get('module_key', '')
        if not isinstance(request.user, User):
            return redirect('login')
        if not mk or not can_access_store_module(request.user, mk):
            messages.error(request, 'Accès non autorisé pour votre rôle.')
            return redirect('dashboard')
        self.module_key = mk
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['store_module_key'] = self.module_key
        ctx['store_module_title'] = STORE_MODULE_LABELS[self.module_key]
        return ctx


class StoreLotsView(StorePlaceholderView):
    module_key = 'lots'


class StoreCaisseView(StorePlaceholderView):
    module_key = 'caisse'


class StoreVentesView(StorePlaceholderView):
    module_key = 'ventes'


class StoreCommandesView(StorePlaceholderView):
    module_key = 'commandes'


class StoreRapportsView(StorePlaceholderView):
    module_key = 'rapports'
