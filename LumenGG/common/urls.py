from django.urls import path

from . import views
from django.contrib.auth import views as auth_views

app_name = 'common'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='mypage'),
    path('profile/<int:id>', views.profile, name='userpage'),
    path('profile/<str:name>/', views.nameToProfile, name='nameToProfile'),
    path('editProfile/', views.editProfile, name='editProfile')
]