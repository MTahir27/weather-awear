from django.urls import include, path

urlpatterns = [
    path("api/", include("trips.api.urls")),
]

handler404 = "trips.api.errors.not_found"
handler500 = "trips.api.errors.server_error"
