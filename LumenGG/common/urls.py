from django.urls import path

from . import views
from django.contrib.auth import views as auth_views

app_name = 'common'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('v2/login/', views.loginV2, name='loginV2'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('v2/signup/', views.signupV2, name='signupV2'),
    path('profile/', views.profile, name='mypage'),
    path('v2/profile/', views.profileV2, name='mypageV2'),
    path('v2/profile/<int:id>', views.profileV2, name='userpageV2'),
    path('v2/profile/<str:name>/', views.nameToProfileV2, name='nameToProfileV2'),
    path('profile/<int:id>', views.profile, name='userpage'),
    path('profile/<str:name>/', views.nameToProfile, name='nameToProfile'),
    path('editProfile/', views.editProfile, name='editProfile')
]
