"""
URL configuration for config project.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('', include('users.urls')),
    path('admin/', admin.site.urls),
]

# MEDIA uploads (articles, logos, preuves).
# Note: django.conf.urls.static.static() ne sert RIEN quand DEBUG=False.
# En prod (Coolify/gunicorn + WhiteNoise), WhiteNoise sert uniquement STATIC,
# donc /media/ doit etre servi explicitement (sinon 404).
urlpatterns += [
    re_path(
        r'^media/(?P<path>.*)$',
        serve,
        {'document_root': settings.MEDIA_ROOT},
    ),
]
