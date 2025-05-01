from django.urls import path

from . import views

app_name = 'battlelog'

urlpatterns = [
    path('sim/', views.sim, name='sim'),
    path('stream/', views.stream, name='stream'),
]