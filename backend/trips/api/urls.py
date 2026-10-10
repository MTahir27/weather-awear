from django.urls import path

from trips.api import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("geocode", views.geocode, name="geocode"),
    path("trips/plan", views.plan_trip, name="plan-trip"),
]
