from django.urls import path

from . import views


app_name = 'rules'

urlpatterns = [
    path('', views.rulebookIndex, name='index'),
    path('manage/', views.ruleManage, name='manage'),
    path('manage/book/<int:pk>/', views.ruleManageBook, name='manageBook'),
    path('manage/rule/<int:pk>/', views.ruleManageRule, name='manageRule'),
    path('manage/rule/<int:pk>/move/<str:direction>/', views.ruleMove, name='ruleMove'),
    path('manage/book/<int:book_pk>/visual/add/', views.rulebookVisualGuideCreate, name='bookVisualCreate'),
    path('manage/book/<int:book_pk>/visual-assets/', views.rulebookVisualAssetsEdit, name='bookVisualAssets'),
    path('manage/rule/<int:rule_pk>/visual/add/', views.ruleVisualGuideCreate, name='visualCreate'),
    path('manage/visual/<int:pk>/edit/', views.ruleVisualGuideEdit, name='visualEdit'),
    path('manage/visual/<int:pk>/delete/', views.ruleVisualGuideDelete, name='visualDelete'),
    path('manage/add/', views.ruleCreate, name='ruleCreate'),
    path('manage/<int:pk>/edit/', views.ruleEdit, name='ruleEdit'),
    path('manage/<int:pk>/delete/', views.ruleDelete, name='ruleDelete'),
    path('guide/', views.rulebookGuide, name='guide'),
    path('comprehensive/', views.rulebookComprehensive, name='comprehensive'),
    path('tournament/', views.rulebookTournament, name='tournament'),
    path('<slug:slug>/', views.rulebookDetail, name='detail'),
]
