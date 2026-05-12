"""
URL configuration for LumenGG project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include, reverse_lazy

from card.sitemaps import StaticSitemap as CardStaticSitemap, CardSitemap
from collection.sitemaps import CollectionSitemap
from common.sitemaps import StaticSitemap as CmnStaticSitemap, UserSitemap
from deck.sitemaps import StaticSitemap as DeckStaticSitemap, DeckSitemap
from qna.sitemaps import StaticSitemap as QnaStaticSitemap, QnaSitemap
from statistic.sitemaps import StaticSitemap as StatStaticSitemap, ChampionshipSitemap

sitemaps = {
    "card-static": CardStaticSitemap,
    "card": CardSitemap,
    "deck-static": DeckStaticSitemap,
    "deck": DeckSitemap,
    "qna-static": QnaStaticSitemap,
    "qna": QnaSitemap,
    "collection": CollectionSitemap,
    "statistic": StatStaticSitemap,
    "championship": ChampionshipSitemap,
    "common": CmnStaticSitemap,
    "user": UserSitemap
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('card.urls'), name='card'),
    path('common/', include('common.urls'), name='common'),
    path('deck/', include('deck.urls'), name='deck'),
    path('qna/', include('qna.urls'), name='qna'),
    path('collection/', include('collection.urls'), name='collection'),
    path('stat/', include('statistic.urls'), name='stat'),
    path('battlelog/', include('battlelog.urls'), name='battlelog'),
    path('tournament/', include('tournament.urls'), name='tournament'),
    path('summernote/', include('django_summernote.urls')),
    
    path(
        'legacy/password_reset/',
        auth_views.PasswordResetView.as_view(success_url=reverse_lazy('password_reset_doneLegacy')),
        name="password_resetLegacy",
    ),
    path('legacy/password_reset_done/', auth_views.PasswordResetDoneView.as_view(), name="password_reset_doneLegacy"),
    path(
        'legacy/password_reset_confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(success_url=reverse_lazy('password_reset_completeLegacy')),
        name="password_reset_confirmLegacy",
    ),
    path('legacy/password_reset_complete/', auth_views.PasswordResetCompleteView.as_view(), name="password_reset_completeLegacy"),
    path(
        'password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form_v2.html',
            email_template_name='registration/password_reset_email_v2.html',
            success_url=reverse_lazy('password_reset_done'),
        ),
        name="password_reset",
    ),
    path(
        'password_reset_done/',
        auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done_v2.html'),
        name="password_reset_done",
    ),
    path(
        'password_reset_confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm_v2.html',
            success_url=reverse_lazy('password_reset_complete'),
        ),
        name="password_reset_confirm",
    ),
    path(
        'password_reset_complete/',
        auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete_v2.html'),
        name="password_reset_complete",
    ),
    path(
        'v2/password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form_v2.html',
            email_template_name='registration/password_reset_email_v2.html',
            success_url=reverse_lazy('password_reset_done'),
        ),
        name="password_resetV2",
    ),
    path(
        'v2/password_reset_done/',
        auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done_v2.html'),
        name="password_reset_doneV2",
    ),
    path(
        'v2/password_reset_confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm_v2.html',
            success_url=reverse_lazy('password_reset_complete'),
        ),
        name="password_reset_confirmV2",
    ),
    path(
        'v2/password_reset_complete/',
        auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete_v2.html'),
        name="password_reset_completeV2",
    ),
    
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap",),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
