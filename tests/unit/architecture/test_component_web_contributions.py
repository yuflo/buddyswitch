"""Typed passive Web route and worker contribution contract."""

from __future__ import annotations

from dataclasses import fields

import pytest


def test_module_assembly_exposes_only_the_two_approved_web_host_seams() -> None:
    from buddyswitch.foundation.composition import ModuleAssembly

    assert [field.name for field in fields(ModuleAssembly)] == [
        "name",
        "daemon_handlers",
        "tools",
        "cli_commands",
        "skills",
        "cleanup",
        "actor_console_sections",
        "inbound_sources",
        "web_routes",
        "web_workers",
    ]


def test_web_contribution_contracts_are_passive_immutable_data() -> None:
    from buddyswitch.launcher import web_contracts

    route_type = getattr(web_contracts, "WebRouteRegistration", None)
    worker_type = getattr(web_contracts, "WebWorkerRegistration", None)
    access_type = getattr(web_contracts, "WebHostAccess", None)
    assert route_type is not None
    assert worker_type is not None
    assert access_type is not None

    route_factory = lambda access: access
    worker_factory = lambda server_url: server_url
    route = route_type(
        name="example-route",
        factory=route_factory,
        exact_paths=("/api/example",),
        prefixes=("/api/example/",),
    )
    worker = worker_type(name="example-worker", factory=worker_factory)
    access = access_type(list_instances=lambda: [])

    assert route.name == "example-route"
    assert route.factory is route_factory
    assert route.exact_paths == ("/api/example",)
    assert route.prefixes == ("/api/example/",)
    assert worker.name == "example-worker"
    assert worker.factory is worker_factory
    assert access.list_instances() == []


def test_application_validates_web_contributions_without_calling_factories() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.foundation.composition import ModuleAssembly
    from buddyswitch.launcher import web_contracts

    route_type = getattr(web_contracts, "WebRouteRegistration", None)
    worker_type = getattr(web_contracts, "WebWorkerRegistration", None)
    assert route_type is not None
    assert worker_type is not None

    calls: list[tuple[str, object]] = []

    def route_factory(access: object) -> object:
        calls.append(("route", access))
        return object()

    def worker_factory(server_url: str) -> object:
        calls.append(("worker", server_url))
        return object()

    application = build_application(
        (
            ModuleAssembly(
                name="example",
                web_routes=(
                    route_type(
                        name="example-route",
                        factory=route_factory,
                        exact_paths=("/api/example",),
                        prefixes=("/api/example/",),
                    ),
                ),
                web_workers=(
                    worker_type(name="example-worker", factory=worker_factory),
                ),
            ),
        ),
        daemon_handler_order=(),
    )

    assert calls == []
    assert application.web_routes[0].factory is route_factory
    assert application.web_workers[0].factory is worker_factory


def test_application_rejects_invalid_and_duplicate_web_contributions() -> None:
    from buddyswitch.application.build import build_application
    from buddyswitch.foundation.composition import ModuleAssembly
    from buddyswitch.launcher import web_contracts

    route_type = getattr(web_contracts, "WebRouteRegistration", None)
    worker_type = getattr(web_contracts, "WebWorkerRegistration", None)
    assert route_type is not None
    assert worker_type is not None

    def route_factory(_access: object) -> object:
        return object()

    def worker_factory(_server_url: str) -> object:
        return object()

    invalid_routes = (
        (
            route_type(name="", factory=route_factory, prefixes=("/api/example/",)),
            "route name",
        ),
        (route_type(name="route", factory=route_factory), "matcher"),
        (
            route_type(name="route", factory=route_factory, exact_paths=("example",)),
            "exact path",
        ),
        (
            route_type(
                name="route",
                factory=route_factory,
                exact_paths=("/api/example?query=1",),
            ),
            "exact path",
        ),
        (
            route_type(name="route", factory=route_factory, prefixes=("/api/example",)),
            "prefix",
        ),
        (
            route_type(
                name="route",
                factory=route_factory,
                prefixes=("/api/example/?query=1",),
            ),
            "prefix",
        ),
        (
            route_type(name="route", factory=None, prefixes=("/api/example/",)),
            "route factory",
        ),
    )
    for registration, message in invalid_routes:
        with pytest.raises(ValueError, match=message):
            build_application(
                (ModuleAssembly(name=f"invalid-{message}", web_routes=(registration,)),),
                daemon_handler_order=(),
            )

    invalid_workers = (
        (worker_type(name="", factory=worker_factory), "worker name"),
        (worker_type(name="worker", factory=None), "worker factory"),
    )
    for registration, message in invalid_workers:
        with pytest.raises(ValueError, match=message):
            build_application(
                (ModuleAssembly(name=f"invalid-{message}", web_workers=(registration,)),),
                daemon_handler_order=(),
            )

    route = route_type(
        name="route",
        factory=route_factory,
        exact_paths=("/api/example",),
        prefixes=("/api/example/",),
    )
    for duplicate in (
        route_type(name="route", factory=route_factory, prefixes=("/api/other/",)),
        route_type(name="other", factory=route_factory, exact_paths=("/api/example",)),
        route_type(name="other", factory=route_factory, prefixes=("/api/example/admin/",)),
        route_type(name="other", factory=route_factory, exact_paths=("/api/example/child",)),
        route_type(name="reserved", factory=route_factory, prefixes=("/api/instances/admin/",)),
    ):
        with pytest.raises(ValueError):
            build_application(
                (
                    ModuleAssembly(name="first", web_routes=(route,)),
                    ModuleAssembly(name="second", web_routes=(duplicate,)),
                ),
                daemon_handler_order=(),
            )

    for overlapping_matchers in (
        route_type(
            name="self-overlap-exact-prefix",
            factory=route_factory,
            exact_paths=("/api/example/child",),
            prefixes=("/api/example/",),
        ),
        route_type(
            name="self-overlap-prefixes",
            factory=route_factory,
            prefixes=("/api/example/", "/api/example/admin/"),
        ),
    ):
        with pytest.raises(ValueError, match="overlapping Web route matchers"):
            build_application(
                (
                    ModuleAssembly(
                        name="self-overlap",
                        web_routes=(overlapping_matchers,),
                    ),
                ),
                daemon_handler_order=(),
            )

    worker = worker_type(name="worker", factory=worker_factory)
    with pytest.raises(ValueError, match="duplicate Web worker"):
        build_application(
            (
                ModuleAssembly(name="first", web_workers=(worker,)),
                ModuleAssembly(name="second", web_workers=(worker,)),
            ),
            daemon_handler_order=(),
        )
