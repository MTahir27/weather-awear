from django.urls import path

from trips.api import views

urlpatterns = [
    path("health", views.health, name="health"),
]
