"""Navigation staff magasin : entrées filtrées par rôle métier."""

from __future__ import annotations

from typing import Any

from users.models import User

# Icônes SVG (chemin path uniquement, viewBox 0 0 24 24)
ICONS = {
    'home': 'M4 10.5L12 4l8 6.5V20a1 1 0 01-1 1h-5v-7H10v7H5a1 1 0 01-1-1v-9.5z',
    'cube': 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4',
    'layers': 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
    'currency': 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    'cart': 'M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H19M17 17a2 2 0 100 4 2 2 0 000-4zM9 17a2 2 0 100 4 2 2 0 000-4z',
    'clipboard': 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
    'chart': 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
    'building': 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
    'user': 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    'users': 'M17 20h5v-2a4 4 0 00-4-4h-1m-4 6H2v-2a4 4 0 014-4h1m6 6v-2a4 4 0 00-4-4H9a4 4 0 00-4 4v2m10-10a4 4 0 11-8 0 4 4 0 018 0zm6 2a3 3 0 11-6 0 3 3 0 016 0z',
}

R_SUPER = User.Role.SUPERADMIN
R_ADMIN = User.Role.ADMIN
R_AGENT = User.Role.AGENT
FULL = (R_SUPER, R_ADMIN)
ALL_STAFF = (R_SUPER, R_ADMIN, R_AGENT)
AGENT_OPS = (R_SUPER, R_ADMIN, R_AGENT)  # ventes, commandes, articles consult, caisse

STAFF_NAV_ENTRIES: list[dict[str, Any]] = [
    {
        'id': 'dashboard',
        'url_name': 'dashboard',
        'label': 'Accueil',
        'icon': 'home',
        'match': ('dashboard',),
        'roles': ALL_STAFF,
    },
    {
        'id': 'articles',
        'url_name': 'store_articles',
        'label': 'Articles',
        'icon': 'cube',
        'match': (
            'store_articles',
            'article_create',
            'article_update',
            'article_delete',
            'article_api_detail',
        ),
        'roles': ALL_STAFF,
    },
    {
        'id': 'lots',
        'url_name': 'store_lots',
        'label': 'Lots',
        'icon': 'layers',
        'match': ('store_lots',),
        'roles': FULL,
    },
    {
        'id': 'caisse',
        'url_name': 'store_caisse',
        'label': 'Caisse',
        'icon': 'currency',
        'match': ('store_caisse',),
        'roles': AGENT_OPS,
    },
    {
        'id': 'ventes',
        'url_name': 'store_ventes',
        'label': 'Ventes',
        'icon': 'cart',
        'match': ('store_ventes',),
        'roles': AGENT_OPS,
    },
    {
        'id': 'commandes',
        'url_name': 'store_commandes',
        'label': 'Commandes',
        'icon': 'clipboard',
        'match': ('store_commandes',),
        'roles': AGENT_OPS,
    },
    {
        'id': 'rapports',
        'url_name': 'store_rapports',
        'label': 'Rapports',
        'icon': 'chart',
        'match': ('store_rapports',),
        'roles': FULL,
    },
    {
        'id': 'clients',
        'url_name': 'store_clients',
        'label': 'Clients',
        'icon': 'users',
        'match': ('store_clients',),
        'roles': FULL,
    },
    {
        'id': 'entreprises',
        'url_name': 'entreprise_list',
        'label': 'Entrep.',
        'icon': 'building',
        'match': ('entreprise_list', 'entreprises_create', 'entreprise_select'),
        'roles': ALL_STAFF,
    },
    {
        'id': 'compte',
        'url_name': 'compte',
        'label': 'Compte',
        'icon': 'user',
        'match': ('compte',),
        'roles': ALL_STAFF,
    },
    {
        'id': 'articles_settings',
        'url_name': 'store_articles_settings',
        'label': 'Paramètres',
        'icon': 'clipboard',
        'match': (
            'store_articles_settings',
            'articles_unite_create',
            'articles_type_create',
            'articles_soustype_create',
        ),
        'roles': ALL_STAFF,
    },
]


def staff_nav_for_user(user) -> list[dict[str, Any]]:
    if not user.is_authenticated or not isinstance(user, User):
        return []
    out = []
    for row in STAFF_NAV_ENTRIES:
        if user.role not in row['roles']:
            continue
        d = dict(row)
        d['path_d'] = ICONS.get(row['icon'], ICONS['home'])
        out.append(d)
    return out


STORE_MODULE_KEYS = frozenset(
    {'articles', 'articles_settings', 'lots', 'caisse', 'ventes', 'commandes', 'rapports', 'clients'},
)

STORE_MODULE_LABELS = {
    'articles': 'Articles',
    'articles_settings': 'Paramètres articles',
    'lots': 'Lots produits',
    'caisse': 'Caisse & sous-comptes',
    'ventes': 'Ventes',
    'commandes': 'Commandes clients',
    'rapports': 'Rapports',
    'clients': 'Clients & garanties',
}

# Agent : pas lots ni rapports (écriture / pilotage étendu)
_AGENT_ALLOWED = frozenset({'articles', 'articles_settings', 'caisse', 'ventes', 'commandes'})


def can_access_store_module(user, module_key: str) -> bool:
    if not user.is_authenticated or not isinstance(user, User):
        return False
    if module_key not in STORE_MODULE_KEYS:
        return False
    if user.is_superadmin_role() or user.is_admin_role():
        return True
    if user.is_agent_role():
        return module_key in _AGENT_ALLOWED
    return False
