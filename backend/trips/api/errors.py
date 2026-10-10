"""JSON error responses for requests that never reach a DRF view."""

from django.http import HttpRequest, JsonResponse


def not_found(request: HttpRequest, exception: Exception) -> JsonResponse:
    return JsonResponse({"detail": "Not found."}, status=404)


def server_error(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"detail": "Internal server error."}, status=500)
