from django.urls import path

from . import views
from django.contrib.auth import views as auth_views

app_name = 'common'

urlpatterns = [
    path('login/', views.loginV2, name='login'),
    path('v2/login/', views.loginV2, name='loginV2'),
    path('legacy/login/', views.loginLegacy, name='legacyLogin'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signupV2, name='signup'),
    path('v2/signup/', views.signupV2, name='signupV2'),
    path('legacy/signup/', views.signupLegacy, name='legacySignup'),
    path('profile/', views.profileV2, name='mypage'),
    path('v2/profile/', views.profileV2, name='mypageV2'),
    path('v2/profile/<int:id>', views.profileV2, name='userpageV2'),
    path('v2/profile/<str:name>/', views.nameToProfileV2, name='nameToProfileV2'),
    path('legacy/profile/', views.profile, name='legacyMypage'),
    path('legacy/profile/<int:id>', views.profile, name='legacyUserpage'),
    path('legacy/profile/<str:name>/', views.nameToProfile, name='legacyNameToProfile'),
    path('profile/<int:id>', views.profileV2, name='userpage'),
    path('profile/<str:name>/', views.nameToProfileV2, name='nameToProfile'),
    path('editProfile/', views.editProfile, name='editProfile')
]
