from django.urls import path
from . import views

app_name = 'missions'
urlpatterns = [
    path('', views.board, name='board'),
    path('new/', views.create, name='create'),
    path('<int:pk>/', views.detail, name='detail'),
    path('<int:pk>/join/', views.join, name='join'),
    path('<int:pk>/invite/', views.invite, name='invite'),
    path('<int:pk>/invitation/', views.respond, name='respond'),
    path('<int:pk>/contribute/', views.contribute, name='contribute'),
    path('<int:pk>/contribution/delete/', views.delete_contribution, name='delete_contribution'),
    path('<int:pk>/close/', views.close, name='close'),
    path('<int:pk>/discussion/', views.discuss, name='discuss'),
    path('<int:pk>/discussion/<int:comment_pk>/delete/', views.delete_discussion, name='delete_discussion'),
    path('<int:pk>/react/<int:contribution_pk>/', views.react, name='react'),
    path('<int:pk>/updates/', views.updates, name='updates'),
    path('<int:pk>/media/<str:kind>/<int:item_pk>/', views.media, name='media'),
]
