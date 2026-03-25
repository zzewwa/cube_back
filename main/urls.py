from django.urls import path

from .views import dashboard_view, login_view, logout_view, register_view


urlpatterns = [
    path('', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('logout/', logout_view, name='logout'),
]