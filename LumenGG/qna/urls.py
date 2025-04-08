from django.urls import path
from . import views

app_name = 'qna'

urlpatterns = [
    path('', views.index, name='index'),
    path('detail/<int:id>/', views.detail, name='detail'),
    path('detail/', views.detail, name='detailEmpty'),
    path('create/', views.create, name='create'),
    path('createSearch/', views.createSearch, name='cardSearch'),
    path('update/<int:id>/', views.update, name='update'),
    path('delete/<int:id>/', views.delete, name='delete'),
    #path('xlsxImport/', views.xlsxImport, name='xlsxImport'),
    
    path('special/', views.special, name='special'),
]