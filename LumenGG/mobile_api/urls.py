from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

app_name = 'mobile_api'
urlpatterns = [
    path('auth/login', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh', TokenRefreshView.as_view(), name='refresh'),
    path('auth/signup', views.signup),
    path('auth/logout', views.logout),
    path('auth/account', views.account),
    path('catalog/manifest', views.manifest, name='manifest'),
    path('catalog/files/<str:version>', views.catalog_file),
    path('catalog/images/<str:filename>', views.catalog_image),
    path('sync', views.sync, name='sync'),
    path('calculators/', views.calculators),
    path('calculators/<str:view_token>/state', views.calculator_state),
    path('calculators/<str:view_token>/events', views.calculator_events),
    path('calculators/<str:view_token>/action', views.calculator_action),
]
