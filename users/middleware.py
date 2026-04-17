from django.contrib import messages
from django.shortcuts import redirect
from django.urls import resolve, reverse

from users.constants import (
    SESSION_ACTIVE_ENTREPRISE_ID,
    SESSION_CLIENT_ACTIVE_ENTREPRISE_ID,
    SESSION_CLIENT_ID,
)
from users.models import AffectationEntreprise, Client, User

CLIENT_PATH_PREFIX = '/fr/client/'
CLIENT_EXEMPT_URL_NAMES = frozenset({'client_login', 'client_logout'})


class EntrepriseSessionMiddleware:
    """
    - Force l'onboarding entreprise si l'utilisateur n'en a aucune.
    - Si plusieurs entreprises : impose la sélection tant qu'aucune n'est active en session.
    - Superadmin technique : pas d'obligation d'entreprise.
    """

    EXEMPT_URL_NAMES = frozenset(
        {
            'login',
            'signup',
            'logout',
        }
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if not isinstance(request.user, User):
            return self.get_response(request)

        if (
            request.path.startswith('/admin/')
            or request.path.startswith('/static/')
            or request.path.startswith('/media/')
        ):
            return self.get_response(request)

        if request.path.startswith('/fr/client/') or request.path.startswith('/fr/register-client'):
            return self.get_response(request)

        if request.user.is_superadmin_role():
            return self.get_response(request)

        try:
            match = resolve(request.path)
            url_name = match.url_name
        except Exception:
            return self.get_response(request)

        if url_name in self.EXEMPT_URL_NAMES:
            return self.get_response(request)

        liens = AffectationEntreprise.objects.filter(source=request.user.pk)
        n = liens.count()
        eid = request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)

        if n == 0:
            if url_name == 'entreprises_create':
                return self.get_response(request)
            return redirect(reverse('entreprises_create'))

        if n == 1:
            only_id = liens.values_list('entreprise_id', flat=True).first()
            if request.session.get(SESSION_ACTIVE_ENTREPRISE_ID) != only_id:
                request.session[SESSION_ACTIVE_ENTREPRISE_ID] = only_id
            return self.get_response(request)

        ids = set(liens.values_list('entreprise_id', flat=True))
        if eid is None or eid not in ids:
            if url_name == 'entreprise_select':
                return self.get_response(request)
            return redirect(reverse('entreprise_select'))

        return self.get_response(request)


class ClientPortalMiddleware:
    """Protège les URLs `/fr/client/*` (sauf login / logout) et fixe l’entreprise active en session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.portal_client = None
        if not request.path.startswith(CLIENT_PATH_PREFIX):
            return self.get_response(request)
        try:
            match = resolve(request.path)
            url_name = match.url_name
        except Exception:
            return self.get_response(request)
        if url_name in CLIENT_EXEMPT_URL_NAMES:
            return self.get_response(request)
        cid = request.session.get(SESSION_CLIENT_ID)
        if not cid:
            return redirect(reverse('client_login'))
        client = Client.objects.filter(pk=cid).first()
        if not client:
            request.session.pop(SESSION_CLIENT_ID, None)
            request.session.pop(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, None)
            return redirect(reverse('client_login'))
        request.portal_client = client
        eids = list(
            AffectationEntreprise.objects.filter(source=client.pk).values_list('entreprise_id', flat=True),
        )
        if not eids:
            request.session.pop(SESSION_CLIENT_ID, None)
            request.session.pop(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, None)
            messages.error(request, 'Aucune entreprise liée à ce compte.')
            return redirect(reverse('client_login'))
        active = request.session.get(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID)
        if len(eids) > 1 and (active is None or int(active) not in set(eids)):
            if url_name != 'client_entreprise_select':
                return redirect(reverse('client_entreprise_select'))
        elif len(eids) == 1:
            only_id = eids[0]
            if request.session.get(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID) != only_id:
                request.session[SESSION_CLIENT_ACTIVE_ENTREPRISE_ID] = only_id
        return self.get_response(request)
