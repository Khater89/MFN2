from django.contrib import admin
from django.urls import path, include

urlpatterns = [path('system-admin/', admin.site.urls), path('', include('marketplace.urls'))]
