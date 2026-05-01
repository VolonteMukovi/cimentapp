from django.urls import path

from fournisseurs import views

urlpatterns = [
    path('', views.FournisseursHomeView.as_view(), name='store_fournisseurs'),
]

