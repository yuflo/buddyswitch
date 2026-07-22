import shlex

from tests.integration.web.management_harness import *  # noqa: F401,F403


class WebManagementHTTPTests(WebManagementServerTestCase):
    def test_health_route_is_read_only(self) -> None:
        runner, base_url = self._start_server()
        status, payload = self._request_json(base_url, method="GET", path="/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(runner.calls, [])

    def test_buddies_route_comes_from_host_control_roles(self) -> None:
        runner = RecordingHostControl()
        runner.roles_response = [
            {
                "id": "pm",
                "label": "PM",
                "scope": "Own product iteration and track progression.",
            },
            {
                "id": "dev",
                "label": "Dev",
                "scope": "Implement approved scope in project code.",
            },
        ]
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(base_url, method="GET", path="/api/roles")
        self.assertEqual(status, 200)
        self.assertEqual(
            payload,
            {
                "ok": True,
                "roles": [
                    {
                        "id": "pm",
                        "label": "PM",
                        "scope": "Own product iteration and track progression.",
                    },
                    {
                        "id": "dev",
                        "label": "Dev",
                        "scope": "Implement approved scope in project code.",
                    },
                ],
            },
        )
        self.assertEqual(runner.calls, [("roles", ())])

    def test_instances_route_preserves_host_control_summary_shape(self) -> None:
        runner = RecordingHostControl()
        runner.list_instances_response = [
            {
                "actor_id": "act-pm-demo",
                "role": "pm",
                "status": "active",
                "app_server_health": "healthy",
                "thread_id": "thread-pm",
                "browser_port": 9222,
                "updated_at": "2026-05-24T10:00:00Z",
                "workspace_dir": "/tmp/shared/instances/act-pm-demo/workspace",
            }
        ]
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(base_url, method="GET", path="/api/instances")
        self.assertEqual(status, 200)
        self.assertEqual(
            payload,
            {
                "ok": True,
                "instances": [
                    {
                        "actor_id": "act-pm-demo",
                        "role": "pm",
                        "status": "active",
                        "app_server_health": "healthy",
                        "thread_id": "thread-pm",
                        "browser_port": 9222,
                        "updated_at": "2026-05-24T10:00:00Z",
                        "workspace_dir": "/tmp/shared/instances/act-pm-demo/workspace",
                    }
                ],
            },
        )
        self.assertEqual(runner.calls, [("list_instances", (None,))])

    def test_status_route_preserves_host_control_status_shape(self) -> None:
        runner = RecordingHostControl()
        runner.status_response = {
            "actor_id": "act-pm-demo",
            "role": "pm",
            "status": "active",
            "workspace_dir": "/tmp/shared/instances/act-pm-demo/workspace",
            "browser_port": 9222,
            "updated_at": "2026-05-24T10:00:00Z",
            "thread_id": "thread-demo",
            "app_server": {"healthy": True},
            "thread": {"status": "idle", "raw": {}},
        }
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(base_url, method="GET", path="/api/instances/act-pm-demo/status")
        self.assertEqual(status, 200)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["instance"]["thread"]["status"], "idle")
        self.assertEqual(payload["instance"]["app_server"]["healthy"], True)
        self.assertEqual(payload["instance"]["thread_id"], "thread-demo")

    def test_create_route_rejects_unknown_role_synchronously_from_host_control_roles(self) -> None:
        host_control = RecordingHostControl()
        _host_control, base_url = self._start_server(host_control)
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances",
            payload={"role": "unknown"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(payload["error"]["message"], "Unknown role: unknown")
        self.assertEqual(host_control.calls, [("roles", ())])

    def test_start_route_returns_operation_before_launcher_finishes(self) -> None:
        runner = RecordingHostControl()
        release_start = threading.Event()
        runner.roles_response = [{"id": "market", "label": "Market", "scope": "research"}]
        runner.block("start", ("market", "act-market-demo"), release_start)
        runner.set_response("start", ("market", "act-market-demo"), {"actor_id": "act-market-demo"})
        runner.set_response("status", ("act-market-demo",), active_status("act-market-demo", "thread-1", "idle"))
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)
        result: dict[str, object] = {}

        def call_start() -> None:
            result["value"] = service.handle_api("POST", "/api/instances", b'{"role":"market"}')

        thread = threading.Thread(target=call_start)
        thread.start()
        try:
            self.assertTrue(
                wait_for_condition(lambda: "value" in result, timeout_seconds=0.2),
                "start route should return before launcher start command is released",
            )
            status, payload = result["value"]  # type: ignore[misc]
            self.assertEqual(status, 202)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["operation"]["action"], "start")
            self.assertIn(payload["operation"]["status"], {"queued", "running"})
            self.assertEqual(payload["operation"]["target"]["role"], "market")
            self.assertEqual(payload["operation"]["target"]["actor_id"], "act-market-demo")
            operation_id = payload["operation"]["id"]
        finally:
            release_start.set()
            thread.join(2)
        operation = wait_for_operation_status(service, operation_id, "succeeded")
        self.assertEqual(operation["target"]["actor_id"], "act-market-demo")
        self.assertEqual(operation["result"]["actor_id"], "act-market-demo")

    def test_start_route_queues_second_start_while_first_is_running(self) -> None:
        runner = RecordingHostControl()
        release_market_start = threading.Event()
        runner.roles_response = [
            {"id": "market", "label": "Market", "scope": "research"},
            {"id": "pm", "label": "PM", "scope": "product"},
        ]
        runner.block("start", ("market", "act-market-demo"), release_market_start)
        runner.set_response("start", ("market", "act-market-demo"), {"actor_id": "act-market-demo"})
        runner.set_response("start", ("pm", "act-pm-demo"), {"actor_id": "act-pm-demo"})
        runner.set_response("status", ("act-market-demo",), active_status("act-market-demo", "thread-market", "idle"))
        runner.set_response("status", ("act-pm-demo",), active_status("act-pm-demo", "thread-pm", "idle"))
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        first_status, first_payload = service.handle_api("POST", "/api/instances", b'{"role":"market"}')
        first_operation_id = first_payload["operation"]["id"]
        wait_for_operation_status(service, first_operation_id, "running")

        second_status, second_payload = service.handle_api("POST", "/api/instances", b'{"role":"pm"}')
        second_operation = second_payload["operation"]

        self.assertEqual(first_status, 202)
        self.assertEqual(second_status, 202)
        self.assertEqual(second_operation["action"], "start")
        self.assertEqual(second_operation["status"], "queued")
        self.assertEqual(second_operation["target"]["role"], "pm")
        self.assertEqual(
            [call for call in runner.calls if call[0] == "start"],
            [("start", ("market", "act-market-demo"))],
        )

        release_market_start.set()
        wait_for_operation_status(service, first_operation_id, "succeeded")
        second_final = wait_for_operation_status(service, second_operation["id"], "succeeded")

        self.assertEqual(second_final["target"]["actor_id"], "act-pm-demo")
        self.assertEqual(second_final["result"]["actor_id"], "act-pm-demo")
        self.assertEqual(
            [call for call in runner.calls if call[0] == "start"],
            [
                ("start", ("market", "act-market-demo")),
                ("start", ("pm", "act-pm-demo")),
            ],
        )

    def test_create_instance_delegates_to_host_control_start_without_initialize_input(self) -> None:
        runner = RecordingHostControl()
        runner.set_response("start", ("pm", "act-pm-demo"), {"actor_id": "act-pm-demo"})
        runner.set_response("status", ("act-pm-demo",), active_status("act-pm-demo", "thread-1", "idle"))
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        status, payload = service.handle_api("POST", "/api/instances", b'{"role":"pm"}')

        self.assertEqual(status, 202)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["operation"]["action"], "start")
        operation = wait_for_operation_status(service, payload["operation"]["id"], "succeeded")
        self.assertEqual(operation["result"]["actor_id"], "act-pm-demo")
        self.assertEqual(operation["result"]["instance"]["thread"]["status"], "idle")
        self.assertEqual(operation["result"]["instance"]["thread_id"], "thread-1")
        self.assertEqual(
            runner.calls,
            [
                ("roles", ()),
                ("allocate_actor_id", ("pm",)),
                ("start", ("pm", "act-pm-demo")),
                ("status", ("act-pm-demo",)),
            ],
        )
        self.assertNotIn("Initialize this " "BuddySwitch thread", json.dumps(runner.calls))

    def test_create_instance_returns_host_control_start_error_without_initialize_retry(self) -> None:
        runner = RecordingHostControl()
        runner.set_error(
            "start",
            ("pm", "act-pm-demo"),
            host_control_error("COMMAND_FAILED", "Thread bootstrap failed for thread-1."),
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        status, payload = service.handle_api("POST", "/api/instances", b'{"role":"pm"}')

        self.assertEqual(status, 202)
        operation = wait_for_operation_status(service, payload["operation"]["id"], "failed")
        self.assertEqual(operation["error"]["code"], "COMMAND_FAILED")
        self.assertIn("Thread bootstrap failed", operation["error"]["message"])
        self.assertEqual(
            runner.calls,
            [("roles", ()), ("allocate_actor_id", ("pm",)), ("start", ("pm", "act-pm-demo"))],
        )

    def test_retry_route_returns_one_operation_with_previous_and_replacement_ids(self) -> None:
        runner = RecordingHostControl()
        failed_actor_id = "act-pm-failed"
        replacement_actor_id = "act-pm-replacement"
        release_retry = threading.Event()
        runner.status_response = failed_status(failed_actor_id)
        runner.set_response(
            "prepare_retry",
            (failed_actor_id,),
            {
                "actor_id": failed_actor_id,
                "replacement_actor_id": replacement_actor_id,
                "role": "pm",
            },
        )
        runner.set_response(
            "retry",
            (failed_actor_id, replacement_actor_id),
            {"previous_actor_id": failed_actor_id, "actor_id": replacement_actor_id, "role": "pm"},
        )
        runner.set_response(
            "status",
            (replacement_actor_id,),
            active_status(replacement_actor_id, "thread-replacement", "idle"),
        )
        runner.block("retry", (failed_actor_id, replacement_actor_id), release_retry)
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        status, payload = service.handle_api(
            "POST",
            f"/api/instances/{failed_actor_id}/retry",
            b"",
        )

        self.assertEqual(status, 202)
        operation = payload["operation"]
        self.assertEqual(operation["action"], "retry")
        self.assertEqual(
            operation["target"],
            {
                "actor_id": failed_actor_id,
                "replacement_actor_id": replacement_actor_id,
                "role": "pm",
            },
        )
        with self.assertRaises(WEB_MANAGEMENT.HttpError) as replacement_conflict:
            service.handle_api("DELETE", f"/api/instances/{replacement_actor_id}", b"")
        self.assertEqual(replacement_conflict.exception.status, 409)
        self.assertEqual(replacement_conflict.exception.code, "BUSY")
        release_retry.set()
        final = wait_for_operation_status(service, operation["id"], "succeeded")
        self.assertEqual(final["target"], operation["target"])
        self.assertEqual(final["result"]["previous_actor_id"], failed_actor_id)
        self.assertEqual(final["result"]["actor_id"], replacement_actor_id)
        self.assertEqual(final["result"]["instance"]["actor_id"], replacement_actor_id)
        self.assertEqual(
            runner.calls,
            [
                ("prepare_retry", (failed_actor_id,)),
                ("retry", (failed_actor_id, replacement_actor_id)),
                ("status", (replacement_actor_id,)),
            ],
        )

    def test_retry_validation_failure_creates_no_operation_or_mutation(self) -> None:
        runner = RecordingHostControl()
        runner.set_error(
            "prepare_retry",
            ("act-pm-stopped",),
            host_control_error(
                "LIFECYCLE_BLOCKED",
                "Retry requires an inactive actor with a recorded start failure.",
                returncode=3,
            ),
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/act-pm-stopped/retry", b"")

        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(raised.exception.code, "LIFECYCLE_BLOCKED")
        self.assertEqual(runner.calls, [("prepare_retry", ("act-pm-stopped",))])
        self.assertEqual(service._operations, {})

    def test_retry_failure_preserves_both_target_ids_without_success_payload(self) -> None:
        runner = RecordingHostControl()
        failed_actor_id = "act-pm-failed"
        replacement_actor_id = "act-pm-replacement"
        runner.set_response(
            "prepare_retry",
            (failed_actor_id,),
            {
                "actor_id": failed_actor_id,
                "replacement_actor_id": replacement_actor_id,
                "role": "pm",
            },
        )
        runner.set_error(
            "retry",
            (failed_actor_id, replacement_actor_id),
            host_control_error("COMMAND_FAILED", "Replacement start failed."),
        )
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        status, payload = service.handle_api("POST", f"/api/instances/{failed_actor_id}/retry", b"")

        self.assertEqual(status, 202)
        final = wait_for_operation_status(service, payload["operation"]["id"], "failed")
        self.assertIsNone(final["result"])
        self.assertEqual(final["target"]["actor_id"], failed_actor_id)
        self.assertEqual(final["target"]["replacement_actor_id"], replacement_actor_id)
        self.assertEqual(final["error"]["message"], "Replacement start failed.")

    def test_clear_route_delegates_to_host_control_clear_without_initialize_input(self) -> None:
        runner = RecordingHostControl()
        runner.set_response(
            "clear",
            ("act-pm-demo",),
            {
                "actor_id": "act-pm-demo",
                "previous_thread_id": "thread-old",
                "thread_id": "thread-new",
            },
        )
        runner.set_response("status", ("act-pm-demo",), active_status("act-pm-demo", "thread-new", "idle"))
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        status, payload = service.handle_api("POST", "/api/instances/act-pm-demo/clear", b"")

        self.assertEqual(status, 202)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["operation"]["action"], "clear")
        operation = wait_for_operation_status(service, payload["operation"]["id"], "succeeded")
        self.assertEqual(operation["result"]["previous_thread_id"], "thread-old")
        self.assertEqual(operation["result"]["thread_id"], "thread-new")
        self.assertEqual(operation["result"]["instance"]["thread_id"], "thread-new")
        self.assertEqual(runner.calls, [("clear", ("act-pm-demo",)), ("status", ("act-pm-demo",))])
        self.assertNotIn("Initialize this " "BuddySwitch thread", json.dumps(runner.calls))

    def test_clear_route_returns_command_failure_when_host_control_clear_fails(self) -> None:
        runner = RecordingHostControl()
        runner.set_error("clear", ("act-pm-demo",), host_control_error("COMMAND_FAILED", "Daemon start failed for act-pm-demo."))
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        status, payload = service.handle_api("POST", "/api/instances/act-pm-demo/clear", b"")

        self.assertEqual(status, 202)
        operation = wait_for_operation_status(service, payload["operation"]["id"], "failed")
        self.assertEqual(operation["error"]["code"], "COMMAND_FAILED")
        self.assertIn("Daemon start failed", operation["error"]["message"])
        self.assertEqual(runner.calls, [("clear", ("act-pm-demo",))])

    def test_unknown_lifecycle_operation_returns_404(self) -> None:
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=RecordingHostControl())

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("GET", "/api/operations/op-missing", b"")

        self.assertEqual(raised.exception.status, 404)
        self.assertEqual(raised.exception.code, "NOT_FOUND")

    def test_initialize_route_is_removed(self) -> None:
        runner = RecordingHostControl()
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/act-pm-demo/" + "initialize", b"")

        self.assertEqual(raised.exception.status, 404)
        self.assertEqual(raised.exception.code, "NOT_FOUND")
        self.assertEqual(runner.calls, [])

    def test_resume_route_delegates_to_host_control_resume(self) -> None:
        runner = RecordingHostControl()
        runner.set_response("resume", ("act-pm-demo",), {"actor_id": "act-pm-demo", "thread_id": "thread-1", "status": "active"})
        runner.set_response("status", ("act-pm-demo",), active_status("act-pm-demo", "thread-1", "idle"))
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        status, payload = service.handle_api("POST", "/api/instances/act-pm-demo/resume", b"")

        self.assertEqual(status, 202)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["operation"]["action"], "resume")
        operation = wait_for_operation_status(service, payload["operation"]["id"], "succeeded")
        self.assertEqual(operation["result"]["instance"]["status"], "active")
        self.assertEqual(runner.calls[0], ("resume", ("act-pm-demo",)))

    def test_resume_operation_records_command_failure_after_acceptance(self) -> None:
        runner = RecordingHostControl()
        runner.set_error("resume", ("act-pm-demo",), host_control_error("COMMAND_FAILED", "thread/resume failed for thread-1"))
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        status, payload = service.handle_api("POST", "/api/instances/act-pm-demo/resume", b"")

        self.assertEqual(status, 202)
        operation = wait_for_operation_status(service, payload["operation"]["id"], "failed")
        self.assertEqual(operation["error"]["code"], "COMMAND_FAILED")
        self.assertIn("thread/resume failed", operation["error"]["message"])

    def test_lifecycle_operation_rejects_second_action_for_same_actor_while_running(self) -> None:
        runner = RecordingHostControl()
        release_stop = threading.Event()
        runner.block("stop", ("act-pm-demo",), release_stop)
        runner.set_response("stop", ("act-pm-demo",), {"actor_id": "act-pm-demo", "status": "inactive"})
        runner.set_response("status", ("act-pm-demo",), active_status("act-pm-demo", "thread-1", "idle"))
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=runner)

        status, payload = service.handle_api("POST", "/api/instances/act-pm-demo/stop", b"")
        self.assertEqual(status, 202)
        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/act-pm-demo/resume", b"")

        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(raised.exception.code, "BUSY")
        self.assertIn("Resume available after Stop completes", raised.exception.message)
        release_stop.set()
        wait_for_operation_status(service, payload["operation"]["id"], "succeeded")

    def test_open_tui_route_requires_web_headers_before_status_lookup(self) -> None:
        for headers in (
            {},
            {"Content-Type": "application/json"},
            {"X-BuddySwitch-Web": "1", "Content-Type": "text/plain"},
        ):
            with self.subTest(headers=headers):
                runner = RecordingHostControl()
                opener = FakeTerminalOpener()
                service = WEB_MANAGEMENT.WebManagementService(
                    repo_root=ROOT,
                    host_control=runner,
                    terminal_opener=opener.open,
                    platform_name="darwin",
                )

                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api("POST", "/api/instances/act-pm-demo/open-tui", b"{}", headers)

                self.assertEqual(raised.exception.status, 400)
                self.assertEqual(raised.exception.code, "INVALID_REQUEST")
                self.assertEqual(runner.calls, [])
                self.assertEqual(opener.commands, [])

    def test_attach_command_route_returns_short_public_cli_without_opening_terminal(self) -> None:
        runner = RecordingHostControl()
        opener = FakeTerminalOpener()
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            host_control=runner,
            terminal_opener=opener.open,
            platform_name="darwin",
        )

        status, payload = service.handle_api(
            "GET",
            "/api/instances/act-pm-demo/attach-command",
            b"",
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            payload,
            {
                "ok": True,
                "actor_id": "act-pm-demo",
                "command": (
                    f"cd {shlex.quote(str(ROOT))} "
                    "&& ./buddyswitch-codex instance attach act-pm-demo"
                ),
            },
        )
        self.assertEqual(runner.calls, [])
        self.assertEqual(opener.commands, [])

    def test_attach_command_route_rejects_invalid_actor_id_without_side_effects(self) -> None:
        runner = RecordingHostControl()
        opener = FakeTerminalOpener()
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            host_control=runner,
            terminal_opener=opener.open,
            platform_name="darwin",
        )

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("GET", "/api/instances/demo/attach-command", b"")

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])
        self.assertEqual(opener.commands, [])

    def test_open_tui_route_rejects_bad_host_or_origin_before_status_lookup(self) -> None:
        for headers in (
            {**OPEN_TUI_HEADERS, "Host": "evil.example"},
            {**OPEN_TUI_HEADERS, "Origin": "https://evil.example"},
            {**OPEN_TUI_HEADERS, "Host": "127.0.0.1:8765", "Origin": "http://localhost:8765"},
            {**OPEN_TUI_HEADERS, "Host": "127.0.0.1:8765", "Origin": "http://127.0.0.1:9999"},
        ):
            with self.subTest(headers=headers):
                runner = RecordingHostControl()
                opener = FakeTerminalOpener()
                service = WEB_MANAGEMENT.WebManagementService(
                    repo_root=ROOT,
                    host_control=runner,
                    terminal_opener=opener.open,
                    platform_name="darwin",
                )

                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api("POST", "/api/instances/act-pm-demo/open-tui", b"{}", headers)

                self.assertEqual(raised.exception.status, 403)
                self.assertEqual(raised.exception.code, "FORBIDDEN")
                self.assertEqual(runner.calls, [])
                self.assertEqual(opener.commands, [])

    def test_open_tui_route_rejects_arbitrary_request_fields_before_status_lookup(self) -> None:
        runner = RecordingHostControl()
        opener = FakeTerminalOpener()
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            host_control=runner,
            terminal_opener=opener.open,
            platform_name="darwin",
        )

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api(
                "POST",
                "/api/instances/act-pm-demo/open-tui",
                b'{"command":"open calculator"}',
                OPEN_TUI_HEADERS,
            )

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])
        self.assertEqual(opener.commands, [])

    def test_open_tui_route_rejects_invalid_actor_id_before_terminal_handoff(self) -> None:
        runner = RecordingHostControl()
        opener = FakeTerminalOpener()
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            host_control=runner,
            terminal_opener=opener.open,
            platform_name="darwin",
        )

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/demo/open-tui", b"{}", OPEN_TUI_HEADERS)

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])
        self.assertEqual(opener.commands, [])

    def test_open_tui_route_rejects_unsupported_os_without_copy_command(self) -> None:
        runner = RecordingHostControl()
        opener = FakeTerminalOpener()
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            host_control=runner,
            terminal_opener=opener.open,
            platform_name="linux",
        )

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/act-pm-demo/open-tui", b"{}", OPEN_TUI_HEADERS)

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "UNSUPPORTED_PLATFORM")
        self.assertEqual(raised.exception.message, "Could not launch Terminal.")
        self.assertIsNone(raised.exception.details)
        self.assertEqual(opener.commands, [])
        self.assertEqual(runner.calls, [])

    def test_open_tui_route_hands_short_cli_command_to_terminal_and_returns_accepted(self) -> None:
        runner = RecordingHostControl()
        opener = FakeTerminalOpener()
        _, base_url = self._start_server(runner, terminal_opener=opener.open, platform_name="darwin")

        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/act-pm-demo/open-tui",
            payload={},
            headers={"X-BuddySwitch-Web": "1", "Origin": base_url},
        )

        self.assertEqual(status, 202)
        self.assertEqual(
            payload,
            {
                "ok": True,
                "actor_id": "act-pm-demo",
                "terminal": "Terminal.app",
                "status": "accepted",
            },
        )
        self.assertEqual(
            opener.commands,
            [f"cd {shlex.quote(str(ROOT))} && ./buddyswitch-codex instance attach act-pm-demo"],
        )
        self.assertEqual(runner.calls, [])

    def test_open_tui_route_maps_terminal_launch_failure(self) -> None:
        runner = RecordingHostControl()
        opener = FakeTerminalOpener(WEB_MANAGEMENT.TerminalOpenError("automation denied"))
        service = WEB_MANAGEMENT.WebManagementService(
            repo_root=ROOT,
            host_control=runner,
            terminal_opener=opener.open,
            platform_name="darwin",
        )

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("POST", "/api/instances/act-pm-demo/open-tui", b"{}", OPEN_TUI_HEADERS)

        self.assertEqual(raised.exception.status, 502)
        self.assertEqual(raised.exception.code, "TERMINAL_LAUNCH_FAILED")
        self.assertEqual(raised.exception.message, "Could not launch Terminal.")
        self.assertIsNone(raised.exception.details)
        self.assertEqual(
            opener.commands,
            [f"cd {shlex.quote(str(ROOT))} && ./buddyswitch-codex instance attach act-pm-demo"],
        )
        self.assertEqual(runner.calls, [])

    def test_input_route_returns_404_without_launcher_call(self) -> None:
        runner, base_url = self._start_server()
        removed_route = "/".join(("", "api", "instances", "act-pm-demo", "input"))
        status, payload = self._request_json(
            base_url,
            method="POST",
            path=removed_route,
            payload={"text": "Advance the brief"},
        )
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")
        self.assertEqual(runner.calls, [])

    def test_web_management_does_not_write_message_rows_or_construct_signals(self) -> None:
        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")

        for forbidden in (
            "env.repos.messages",
            "create_message",
            "save_message",
            "delete_message",
            "message." + "available",
            "signal_id",
            "daemon_client.deliver_signal",
            "Instance " + "input blocked:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_web_management_product_api_boundaries_do_not_import_tool_handlers_or_track_service(self) -> None:
        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")

        for forbidden in (
            "env.tools.track" + "._impl",
            "env.services" + ".tracks",
            "dispatch_env_tool_request",
            "dispatch_runtime_request",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

        self.assertFalse((ROOT / "scripts/env/services/tracks.py").exists())

    def test_web_management_has_no_public_side_runtime_surface(self) -> None:
        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")

        for forbidden in (
            "import actor_side_thread",
            "import side_thread_lifecycle",
            '"/' + 'side"',
            '"/' + 'side/close"',
            "start_actor_side_thread",
            "send_to_side_thread",
            "cleanup_side_thread",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_web_management_service_receives_host_control_dependency(self) -> None:
        parameters = inspect.signature(WEB_MANAGEMENT.WebManagementService).parameters

        self.assertIn("host_control", parameters)
        self.assertNotIn("command_runner", parameters)

    def test_web_lifecycle_routes_call_injected_host_control_not_shell_commands(self) -> None:
        host_control = RecordingHostControl()
        host_control.status_response = active_status("act-pm-demo", "thread-main", "stopped")
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=host_control)

        status, payload = service.handle_api("POST", "/api/instances/act-pm-demo/stop", b"")

        self.assertEqual(status, 202)
        operation = wait_for_operation_status(service, payload["operation"]["id"], "succeeded")
        self.assertEqual(operation["result"]["instance"]["thread"]["status"], "stopped")
        self.assertEqual(host_control.calls, [("stop", ("act-pm-demo",)), ("status", ("act-pm-demo",))])

    def test_im_routes_delegate_to_im_http_router_without_host_control_calls(self) -> None:
        class RecordingImRouter:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str, bytes, Mapping[str, str] | None]] = []

            def handle(
                self,
                method: str,
                path: str,
                body: bytes,
                headers: Mapping[str, str] | None,
            ) -> tuple[int, dict[str, object]]:
                self.calls.append((method, path, body, headers))
                return 209, {"ok": True, "owner": "im-router"}

        host_control = RecordingHostControl()
        router = RecordingImRouter()
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=host_control)
        service._im_router = router

        status, payload = service.handle_api(
            "POST",
            "/api/im/messages?trace=1",
            b'{"content":"ping"}',
            {"X-Test": "1"},
        )

        self.assertEqual(status, 209)
        self.assertEqual(payload, {"ok": True, "owner": "im-router"})
        self.assertEqual(router.calls, [("POST", "/api/im/messages?trace=1", b'{"content":"ping"}', {"X-Test": "1"})])
        self.assertEqual(host_control.calls, [])

    def test_create_route_delegates_role_validation_to_injected_host_control(self) -> None:
        host_control = RecordingHostControl()
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=host_control)

        status, payload = service.handle_api("POST", "/api/instances", b'{"role":"pm"}')

        self.assertEqual(status, 202)
        operation = wait_for_operation_status(service, payload["operation"]["id"], "succeeded")
        self.assertEqual(operation["result"]["actor_id"], "act-pm-demo")
        self.assertEqual(
            host_control.calls,
            [
                ("roles", ()),
                ("allocate_actor_id", ("pm",)),
                ("start", ("pm", "act-pm-demo")),
                ("status", ("act-pm-demo",)),
            ],
        )

    def test_status_route_delegates_actor_validation_to_injected_host_control(self) -> None:
        class RejectingHostControl(RecordingHostControl):
            def status(self, actor_id: str) -> dict[str, object]:
                self.calls.append(("status", (actor_id,)))
                raise WEB_MANAGEMENT.host_control_module.HostControlError(
                    "INVALID_REQUEST",
                    "Invalid actor id.",
                    returncode=2,
                )

        host_control = RejectingHostControl()
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=host_control)

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("GET", "/api/instances/not-an-actor/status", b"")

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "INVALID_REQUEST")
        self.assertEqual(host_control.calls, [("status", ("not-an-actor",))])

    def test_web_management_source_does_not_execute_public_cli(self) -> None:
        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")

        self.assertNotIn("Launcher" + "CommandRunner", source)
        self.assertNotIn("--" + "json", source)
        self.assertNotIn('subprocess.run(["./buddyswitch-codex"', source)
        self.assertNotIn('subprocess.Popen(["./buddyswitch-codex"', source)

    def test_web_management_product_api_does_not_split_first_cut_subpanel_routes(self) -> None:
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=RecordingHostControl())

        for path in (
            "/api/actors/act-pm-demo/tasks",
            "/api/actors/act-pm-demo/tracks",
            "/api/tracks/track-alpha/comments",
        ):
            with self.subTest(path=path):
                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api("GET", path, b"")
                self.assertEqual(raised.exception.status, 404)

    def test_web_management_has_no_task_or_track_mutation_routes(self) -> None:
        service = WEB_MANAGEMENT.WebManagementService(repo_root=ROOT, host_control=RecordingHostControl())

        for method, path in (
            ("POST", "/api/tasks"),
            ("PUT", "/api/tasks/task-alpha"),
            ("PATCH", "/api/tasks/task-alpha"),
            ("DELETE", "/api/tasks/task-alpha"),
            ("POST", "/api/tracks"),
            ("PUT", "/api/tracks/track-alpha"),
            ("PATCH", "/api/tracks/track-alpha"),
            ("DELETE", "/api/tracks/track-alpha"),
        ):
            with self.subTest(method=method, path=path):
                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api(method, path, b"{}")
                self.assertEqual(raised.exception.status, 404)
                self.assertEqual(raised.exception.code, "NOT_FOUND")
