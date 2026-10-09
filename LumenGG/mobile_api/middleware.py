"""Serialize legacy web mutations with mobile arrival-ordered synchronization."""
from django.contrib.auth import get_user_model
from django.db import transaction


class AccountWriteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}
                and request.user.is_authenticated
                and request.path.startswith(('/deck/', '/collection/', '/common/'))):
            with transaction.atomic():
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                return self.get_response(request)
        return self.get_response(request)
