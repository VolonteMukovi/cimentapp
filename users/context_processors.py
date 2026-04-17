from users.constants import (
    SESSION_ACTIVE_ENTREPRISE_ID,
    SESSION_CLIENT_ACTIVE_ENTREPRISE_ID,
    SESSION_CLIENT_ID,
)
from users.models import AffectationEntreprise, Client, Entreprise, User
from users.navigation import staff_nav_for_user


def active_entreprise(request):
    """Expose l'entreprise active (filtrage métier) dans tous les templates."""
    if not request.user.is_authenticated:
        return {'active_entreprise': None, 'user_entreprise_count': 0}

    liens = AffectationEntreprise.objects.filter(source=request.user.pk)
    count = liens.count()
    eid = request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
    entreprise = None

    if eid is not None:
        if liens.filter(entreprise_id=eid).exists():
            try:
                entreprise = Entreprise.objects.get(pk=eid)
            except Entreprise.DoesNotExist:
                pass
        else:
            request.session.pop(SESSION_ACTIVE_ENTREPRISE_ID, None)

    return {
        'active_entreprise': entreprise,
        'user_entreprise_count': count,
    }


def staff_navigation(request):
    """Items de barre du bas staff (filtrés par rôle)."""
    if not request.user.is_authenticated or not isinstance(request.user, User):
        return {'staff_nav_items': []}
    return {'staff_nav_items': staff_nav_for_user(request.user)}


def client_portal(request):
    """Données portail client (session) — uniquement sous /fr/client/."""
    if not str(request.path).startswith('/fr/client/'):
        return {'portal_client': None, 'portal_entreprise': None}
    cid = request.session.get(SESSION_CLIENT_ID)
    if not cid:
        return {'portal_client': None, 'portal_entreprise': None}
    client = Client.objects.filter(pk=cid).first()
    if not client:
        return {'portal_client': None, 'portal_entreprise': None}
    eid = request.session.get(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID)
    entreprise = None
    if eid is not None:
        if AffectationEntreprise.objects.filter(source=client.pk, entreprise_id=eid).exists():
            try:
                entreprise = Entreprise.objects.get(pk=eid)
            except Entreprise.DoesNotExist:
                pass
        else:
            request.session.pop(SESSION_CLIENT_ACTIVE_ENTREPRISE_ID, None)
    return {'portal_client': client, 'portal_entreprise': entreprise}
