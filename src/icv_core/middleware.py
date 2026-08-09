"""Middleware for icv-core."""

import contextvars

from asgiref.sync import iscoroutinefunction, markcoroutinefunction

_current_user: contextvars.ContextVar = contextvars.ContextVar("icv_core_current_user", default=None)


def get_current_user():
    """
    Return the current request user set by CurrentUserMiddleware.

    Returns None outside of a request context (e.g., management commands,
    Celery tasks). Always returns None if CurrentUserMiddleware is not active.
    """
    return _current_user.get()


class CurrentUserMiddleware:
    """
    Makes the current request user available to models for
    created_by/updated_by population.

    Required when ICV_CORE_TRACK_CREATED_BY=True. Must be placed after
    Django's AuthenticationMiddleware in the MIDDLEWARE setting.

    Uses a ``contextvars.ContextVar`` rather than ``threading.local()`` so
    that concurrent requests handled on the same thread under ASGI (async
    views, or sync views wrapped by ``sync_to_async``) each get their own
    isolated value. A thread-local would leak one request's user into a
    concurrently-running request sharing that thread, which is a security
    bug for anything gated on the current user (created_by/updated_by
    attribution, audit logging). ``ContextVar`` is copied into each new
    ``asyncio.Task``'s context, so concurrent tasks never see each other's
    value, while synchronous (WSGI) requests keep working exactly as before
    because each thread still gets its own default context.

    Supports both sync and async request pipelines via
    ``asgiref.sync.iscoroutinefunction``/``markcoroutinefunction``, matching
    Django's documented pattern for dual sync/async middleware, so it does
    not force Django to wrap an otherwise-fully-async stack in sync-only
    adapters.

    Example::

        MIDDLEWARE = [
            ...
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "icv_core.middleware.CurrentUserMiddleware",
            ...
        ]
    """

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    def __call__(self, request):
        if iscoroutinefunction(self.get_response):
            return self.__acall__(request)

        token = _current_user.set(getattr(request, "user", None))
        try:
            response = self.get_response(request)
        finally:
            _current_user.reset(token)
        return response

    async def __acall__(self, request):
        token = _current_user.set(getattr(request, "user", None))
        try:
            response = await self.get_response(request)
        finally:
            _current_user.reset(token)
        return response

    def process_exception(self, request, exception) -> None:
        """Clear the context var on unhandled exceptions.

        Django only calls process_exception on middleware that defines it,
        and only for the synchronous exception-handling path. The __call__/
        __acall__ finally blocks above are the primary reset mechanism and
        cover this case too; this method exists for symmetry with the
        previous API and for code paths that invoke it directly (as the
        existing test suite does).
        """
        _current_user.set(None)
