from django.urls import path
from . import views

app_name = 'qna'

urlpatterns = [
    path('', views.indexV2, name='index'),
    path('v2/', views.indexV2, name='indexV2'),
    path('legacy/', views.index, name='legacyIndex'),
    path('legacy/detail/<int:id>/', views.detail, name='legacyDetail'),
    path('legacy/detail/', views.detail, name='legacyDetailEmpty'),
    path('legacy/create/', views.create, name='legacyCreate'),
    path('legacy/update/<int:id>/', views.update, name='legacyUpdate'),
    path('v2/detail/<int:id>/', views.detailV2, name='detailV2'),
    path('v2/create/', views.createV2, name='createV2'),
    path('v2/update/<int:id>/', views.updateV2, name='updateV2'),
    path('detail/<int:id>/', views.detailV2, name='detail'),
    path('detail/', views.detailV2, name='detailEmpty'),
    path('create/', views.createV2, name='create'),
    path('createSearch/', views.createSearch, name='cardSearch'),
    path('update/<int:id>/', views.updateV2, name='update'),
    path('delete/<int:id>/', views.delete, name='delete'),
    #path('xlsxImport/', views.xlsxImport, name='xlsxImport'),
    
    path('special/', views.special, name='special'),
]
