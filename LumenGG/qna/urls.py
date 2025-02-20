from django.urls import path
from . import views

app_name = 'qna'

urlpatterns = [
    path('', views.index, name='index'),
    path('detail/<int:id>/', views.detail, name='detail'),
    path('detail/', views.detail, name='detailEmpty'),
    #path('xlsxImport/', views.xlsxImport, name='xlsxImport'),
]