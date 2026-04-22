from django.urls import include, path

from users import client_views, store_views, views

urlpatterns = [
    path('fr/register-client/<int:entreprise_id>/', client_views.RegisterClientView.as_view(), name='register_client'),
    path('fr/client/login/', client_views.ClientLoginView.as_view(), name='client_login'),
    path('fr/client/logout/', client_views.ClientLogoutView.as_view(), name='client_logout'),
    path('fr/client/catalogue/', client_views.ClientCatalogView.as_view(), name='client_catalogue'),
    path('fr/client/commandes/', include('commandes.client_urls')),
    path('fr/client/transactions/', client_views.ClientTransactionsView.as_view(), name='client_transactions'),
    path('fr/client/caisse/', client_views.ClientWalletView.as_view(), name='client_wallet'),
    path('fr/client/choisir-entreprise/', client_views.ClientEntrepriseSelectView.as_view(), name='client_entreprise_select'),
    path('fr/client/', client_views.ClientPortalHomeView.as_view(), name='client_portal_home'),
    path('', views.HomeRedirectView.as_view(), name='home'),
    path('accounts/login/', views.AppLoginView.as_view(), name='login'),
    path('accounts/logout/', views.AppLogoutView.as_view(), name='logout'),
    path('accounts/signup/', views.SignupView.as_view(), name='signup'),
    path('entreprises/nouvelle/', views.EntrepriseCreateView.as_view(), name='entreprises_create'),
    path('entreprises/', views.EntrepriseListView.as_view(), name='entreprise_list'),
    path('entreprises/choisir/', views.EntrepriseSelectView.as_view(), name='entreprise_select'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('magasin/articles/', include('articles.urls')),
    path('magasin/lots/', include('lots.urls')),
    path('magasin/caisse/', include('caisse.urls')),
    path('magasin/ventes/', include('ventes.urls')),
    path('magasin/commandes/', include('commandes.urls')),
    path('magasin/clients/', include('clients.urls')),
    path('magasin/rapports/', include('rapports.urls')),
    path('activite/', views.ActivityPlaceholderView.as_view(), name='activite'),
    path('compte/', views.AccountView.as_view(), name='compte'),
]
