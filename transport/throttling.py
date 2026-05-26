"""Limitation simple du débit pour les endpoints sensibles."""

from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse


def rate_limit(*, limit: int = 120, window: int = 3600):
    """Limite le nombre d'appels par utilisateur (ou IP) sur une fenêtre glissante."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.is_authenticated:
                ident = f"user:{request.user.pk}"
            else:
                ident = f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"

            key = f"rl:{view_func.__name__}:{ident}"
            count = cache.get(key, 0)
            if count >= limit:
                return JsonResponse(
                    {"detail": "Too many requests. Réessayez plus tard."},
                    status=429,
                )
            cache.set(key, count + 1, window)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
