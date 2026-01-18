from django.contrib import admin
from django.urls import path
from bot_engine import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]