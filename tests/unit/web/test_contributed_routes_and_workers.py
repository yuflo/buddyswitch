"""Generic WebHost behavior for contributed routes and optional workers."""

from __future__ import annotations

from unittest import mock

import pytest


def _contracts():
    from buddyswitch.launcher import web_contracts

    route_type = getattr(web_contracts, "WebRouteRegistration", None)
    worker_type = getattr(web_contracts, "WebWorkerRegistration", None)
    assert route_type is not None
    assert worker_type is not None
    return route_type, worker_type


def test_contributed_route_is_instantiated_prepared_and_dispatched() -> None:
    from buddyswitch.launcher import web_management

    route_type, _worker_type = _contracts()
    calls: list[tuple[str, object]] = []

    class Route:
        def prepare(self) -> None:
            calls.append(("prepare", None))

        def handle(self, method, path, body, headers):
            calls.append(("handle", (method, path, body, headers)))
            return 209, {"ok": True, "owner": "example"}

    def factory(access):
        calls.append(("factory", access.list_instances))
        return Route()

    service = web_management.WebManagementService(
        web_routes=(
            route_type(
                name="example",
                factory=factory,
                exact_paths=("/api/example",),
                prefixes=("/api/example/",),
            ),
        ),
    )
    assert [kind for kind, _value in calls] == ["factory"]

    service.prepare_routes()
    exact_result = service.handle_api(
        "GET",
        "/api/example?trace=exact",
        b"",
        {"X-Test": "exact"},
    )
    prefix_result = service.handle_api(
        "POST",
        "/api/example/action?trace=1",
        b'{"value":1}',
        {"X-Test": "1"},
    )

    assert exact_result == (209, {"ok": True, "owner": "example"})
    assert prefix_result == (209, {"ok": True, "owner": "example"})
    with pytest.raises(web_management.HttpError) as raised:
        service.handle_api("GET", "/api/example-extra", b"", None)
    assert raised.value.status == 404
    assert raised.value.code == "NOT_FOUND"
    assert raised.value.message == "API route not found."
    assert [kind for kind, _value in calls] == [
        "factory",
        "prepare",
        "handle",
        "handle",
    ]


def test_route_preparation_failure_is_not_published_as_ready() -> None:
    from buddyswitch.launcher import web_management

    route_type, _worker_type = _contracts()

    class Route:
        def prepare(self) -> None:
            raise RuntimeError("route unavailable")

        def handle(self, method, path, body, headers):
            raise AssertionError((method, path, body, headers))

    service = web_management.WebManagementService(
        web_routes=(
            route_type(
                name="unavailable",
                factory=lambda _access: Route(),
                prefixes=("/api/unavailable/",),
            ),
        ),
    )

    with pytest.raises(RuntimeError, match="route unavailable"):
        service.prepare_routes()


def test_workers_start_fail_soft_stop_in_reverse_and_close_server_last() -> None:
    from buddyswitch.launcher import web_management

    events: list[str] = []

    class StopServer(Exception):
        pass

    class Server:
        def serve_forever(self) -> None:
            events.append("serve")
            raise StopServer()

        def server_close(self) -> None:
            events.append("close")

    class Worker:
        def __init__(self, name: str, *, fail: bool = False) -> None:
            self.name = name
            self.fail = fail

        def start(self) -> None:
            events.append(f"start:{self.name}")
            if self.fail:
                raise RuntimeError(f"{self.name} unavailable")

        def stop(self) -> None:
            events.append(f"stop:{self.name}")

    workers = (Worker("first"), Worker("failed", fail=True), Worker("last"))
    with mock.patch("sys.stderr") as stderr, pytest.raises(StopServer):
        web_management.serve_with_workers(Server(), workers)

    assert events == [
        "start:first",
        "start:failed",
        "start:last",
        "serve",
        "stop:last",
        "stop:first",
        "close",
    ]
    stderr.write.assert_any_call(
        "Web worker 'failed' disabled: failed unavailable\n"
    )


def test_worker_factories_receive_bound_server_url_only_when_instantiated() -> None:
    from buddyswitch.launcher import web_management

    _route_type, worker_type = _contracts()
    calls: list[str] = []

    class Worker:
        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

    registration = worker_type(
        name="example-worker",
        factory=lambda server_url: calls.append(server_url) or Worker(),
    )
    assert calls == []

    workers = web_management.instantiate_web_workers(
        (registration,),
        "http://127.0.0.1:8765",
    )

    assert calls == ["http://127.0.0.1:8765"]
    assert len(workers) == 1
    assert workers[0].name == "example-worker"
