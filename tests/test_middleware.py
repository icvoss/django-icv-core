"""Tests for icv-core middleware."""

import asyncio

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from icv_core.middleware import CurrentUserMiddleware, _current_user, get_current_user


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture(autouse=True)
def _reset_current_user():
    """Ensure a clean context var before and after each test."""
    token = _current_user.set(None)
    yield
    _current_user.reset(token)


class TestCurrentUserMiddleware:
    """CurrentUserMiddleware stores and clears the request user."""

    def test_get_current_user_returns_none_outside_request(self):
        assert get_current_user() is None

    def test_sync_call_sets_user_for_the_duration_of_the_request(self, rf):
        request = rf.get("/")
        request.user = AnonymousUser()
        seen_user = {}

        def get_response(req):
            seen_user["user"] = get_current_user()
            from django.http import HttpResponse

            return HttpResponse()

        middleware = CurrentUserMiddleware(get_response=get_response)
        middleware(request)

        assert seen_user["user"] is request.user

    def test_sync_call_clears_user_after_the_response_is_returned(self, rf):
        request = rf.get("/")
        request.user = AnonymousUser()

        def get_response(req):
            from django.http import HttpResponse

            return HttpResponse()

        middleware = CurrentUserMiddleware(get_response=get_response)
        middleware(request)

        assert get_current_user() is None

    def test_sync_call_clears_user_even_if_get_response_raises(self, rf):
        request = rf.get("/")
        request.user = AnonymousUser()

        def get_response(req):
            raise ValueError("oops")

        middleware = CurrentUserMiddleware(get_response=get_response)
        with pytest.raises(ValueError, match="oops"):
            middleware(request)

        assert get_current_user() is None

    def test_process_exception_clears_user(self, rf):
        request = rf.get("/")
        request.user = AnonymousUser()
        middleware = CurrentUserMiddleware(get_response=lambda r: None)
        _current_user.set(request.user)
        middleware.process_exception(request, ValueError("oops"))
        assert get_current_user() is None

    def test_get_current_user_returns_none_when_no_user_attr(self, rf):
        request = rf.get("/")
        # No user attribute on request
        middleware = CurrentUserMiddleware(get_response=lambda r: None)
        middleware(request)
        assert get_current_user() is None


class TestCurrentUserMiddlewareAsyncSafety:
    """Regression tests for #13: contextvars must isolate concurrent async requests."""

    def test_middleware_marks_itself_coroutine_capable_for_async_get_response(self):
        async def async_get_response(request):
            from django.http import HttpResponse

            return HttpResponse()

        middleware = CurrentUserMiddleware(get_response=async_get_response)

        assert asyncio.iscoroutinefunction(middleware)

    def test_concurrent_async_requests_do_not_leak_user_identity(self, rf):
        """Two overlapping async requests must never observe each other's user.

        This is the exact failure mode of a threading.local()-backed
        implementation: under ASGI, concurrent requests can run as
        interleaved asyncio.Tasks on the same OS thread (directly, or via
        Django's sync_to_async/async_to_sync bridging). A thread-local is
        shared by every task on that thread, so the second request's
        process_request write can clobber the first request's value while
        the first request is still awaiting its own downstream response.
        contextvars.ContextVar isolates each Task's value instead.
        """

        class FakeUser:
            def __init__(self, name):
                self.name = name

            def __repr__(self):
                return f"FakeUser({self.name!r})"

        user_a = FakeUser("alice")
        user_b = FakeUser("bob")

        request_a = rf.get("/a")
        request_a.user = user_a
        request_b = rf.get("/b")
        request_b.user = user_b

        observed: dict[str, object] = {}

        async def get_response(request):
            from django.http import HttpResponse

            # Yield control mid-request so the other request's task can run
            # and, under the old threading.local implementation, clobber
            # the shared value while this task is still "inside" its request.
            await asyncio.sleep(0)
            observed[request.path] = get_current_user()
            await asyncio.sleep(0)
            return HttpResponse()

        middleware = CurrentUserMiddleware(get_response=get_response)

        async def run_both():
            await asyncio.gather(
                middleware(request_a),
                middleware(request_b),
            )

        asyncio.run(run_both())

        assert observed["/a"] is user_a
        assert observed["/b"] is user_b
        assert get_current_user() is None
