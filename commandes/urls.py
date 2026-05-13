from django.urls import path

from commandes import views


urlpatterns = [
    path('', views.StoreCommandesView.as_view(), name='store_commandes'),
    path('api/commandes/', views.CommandesApiListView.as_view(), name='api_commandes_list'),
    path('api/commandes/<str:commande_id>/confirmer-depot/', views.CommandeConfirmerDepotApiView.as_view(), name='api_commande_confirmer_depot'),
    path('api/commandes/<str:commande_id>/creer-vente/', views.CommandeCreerVenteApiView.as_view(), name='api_commande_creer_vente'),
    path('api/dettes/paiements/', views.DettesPaiementsApiListView.as_view(), name='api_dettes_paiements_list'),
    path('api/dettes/paiements/<int:paiement_id>/confirmer/', views.DettePaiementConfirmerApiView.as_view(), name='api_dette_paiement_confirmer'),
]

