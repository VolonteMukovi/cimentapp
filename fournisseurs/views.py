from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView

from fournisseurs.forms import FournisseurForm
from fournisseurs.models import Fournisseur
from users.constants import SESSION_ACTIVE_ENTREPRISE_ID
from users.models import User
from users.navigation import can_access_store_module


class FournisseursAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not isinstance(request.user, User):
            return self.handle_no_permission()
        if not can_access_store_module(request.user, 'fournisseurs'):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def entreprise_id(self) -> int | None:
        eid = self.request.session.get(SESSION_ACTIVE_ENTREPRISE_ID)
        return int(eid) if eid is not None else None


class FournisseursHomeView(FournisseursAccessMixin, TemplateView):
    template_name = 'fournisseurs/fournisseurs_home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        eid = self.entreprise_id()
        ctx['store_module_key'] = 'fournisseurs'
        ctx['store_module_title'] = 'Fournisseurs'
        ctx['form'] = FournisseurForm()
        ctx['fournisseurs'] = (
            Fournisseur.objects.filter(entreprise_id=eid).order_by('-date_creation') if eid else Fournisseur.objects.none()
        )
        return ctx

    def post(self, request, *args, **kwargs):
        eid = self.entreprise_id()
        if eid is None:
            messages.error(request, 'Veuillez sélectionner une entreprise active avant d’enregistrer un fournisseur.')
            return redirect('store_fournisseurs')

        action = (request.POST.get('action') or 'create').strip().lower()

        if action == 'delete':
            fournisseur_id = request.POST.get('fournisseur_id')
            fournisseur = Fournisseur.objects.filter(pk=fournisseur_id, entreprise_id=eid).first()
            if not fournisseur:
                messages.error(request, 'Fournisseur introuvable.')
                return redirect('store_fournisseurs')
            nom = fournisseur.nom
            fournisseur.delete()
            messages.success(request, f'Fournisseur « {nom} » supprimé.')
            return redirect('store_fournisseurs')

        if action == 'update':
            fournisseur_id = request.POST.get('fournisseur_id')
            fournisseur = Fournisseur.objects.filter(pk=fournisseur_id, entreprise_id=eid).first()
            if not fournisseur:
                messages.error(request, 'Fournisseur introuvable.')
                return redirect('store_fournisseurs')
            form = FournisseurForm(request.POST, instance=fournisseur)
            if form.is_valid():
                fournisseur = form.save()
                messages.success(request, f'Fournisseur « {fournisseur.nom} » modifié.')
                return redirect('store_fournisseurs')
            messages.error(request, 'Modification invalide. Vérifiez les champs saisis.')
            return redirect('store_fournisseurs')

        form = FournisseurForm(request.POST)
        if form.is_valid():
            fournisseur = form.save(commit=False)
            fournisseur.entreprise_id = eid
            fournisseur.save()
            messages.success(request, f'Fournisseur « {fournisseur.nom} » enregistré.')
            return redirect('store_fournisseurs')

        ctx = self.get_context_data(**kwargs)
        ctx['form'] = form
        return self.render_to_response(ctx)

