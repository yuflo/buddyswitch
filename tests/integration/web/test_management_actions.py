from tests.integration.web.management_harness import *  # noqa: F401,F403


class WebManagementHTTPActionTests(WebManagementServerTestCase):
    def test_capabilities_put_route_accepts_http_put_method(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            shared_root = Path(temp_root) / "shared-root"
            write_web_capability_instance(shared_root)
            original_shared_root = os.environ.get("BUDDYSWITCH_SHARED_ROOT")
            os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
            self.addCleanup(_restore_env_value, "BUDDYSWITCH_SHARED_ROOT", original_shared_root)
            _runner, base_url = self._start_server()

            status, payload = self._request_json(
                base_url,
                method="PUT",
                path="/api/actors/act-pm-demo/capabilities",
                payload={"parent": "deep", "side": "maximum"},
            )

            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["actor_id"], "act-pm-demo")
            self.assertEqual(payload["capabilities"]["parent"]["level"], "deep")
            self.assertEqual(payload["capabilities"]["side"]["level"], "maximum")

    def test_side_routes_are_not_public_web_api(self) -> None:
        runner, base_url = self._start_server()
        for path, payload_body in (
            ("/api/instances/act-pm-demo/" + "side", {"text": "Explore"}),
            ("/api/instances/act-pm-demo/" + "side/close", {"side_thread_id": "thread-side-1"}),
        ):
            with self.subTest(path=path):
                status, payload = self._request_json(
                    base_url,
                    method="POST",
                    path=path,
                    payload=payload_body,
                )
                self.assertEqual(status, 404)
                self.assertEqual(payload["error"]["code"], "NOT_FOUND")
        self.assertEqual(runner.calls, [])

    def test_interrupt_route_delegates_and_parses_turn_id(self) -> None:
        runner = RecordingHostControl()
        runner.set_response("interrupt", ("act-pm-demo",), {"actor_id": "act-pm-demo", "thread_id": "thread-demo", "turn_id": "turn-demo"})
        runner.set_response(
            "status",
            ("act-pm-demo",),
            {
                "actor_id": "act-pm-demo",
                "role": "pm",
                "status": "active",
                "workspace_dir": "/tmp/shared/instances/act-pm-demo/workspace",
                "browser_port": 9222,
                "updated_at": "2026-05-24T10:00:00Z",
                "thread_id": "thread-demo",
                "app_server": {"healthy": True},
                "thread": {"status": "interrupted", "raw": {}},
            },
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/act-pm-demo/interrupt",
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["turn_id"], "turn-demo")
        self.assertEqual(payload["instance"]["thread"]["status"], "interrupted")
        self.assertEqual(
            runner.calls,
            [
                ("interrupt", ("act-pm-demo",)),
                ("status", ("act-pm-demo",)),
            ],
        )

    def test_stop_route_delegates_and_refreshes_status(self) -> None:
        runner = RecordingHostControl()
        runner.set_response("stop", ("act-pm-demo",), {"actor_id": "act-pm-demo", "status": "inactive"})
        runner.set_response(
            "status",
            ("act-pm-demo",),
            {
                "actor_id": "act-pm-demo",
                "role": "pm",
                "status": "inactive",
                "workspace_dir": "/tmp/shared/instances/act-pm-demo/workspace",
                "browser_port": 9222,
                "updated_at": "2026-05-24T10:00:00Z",
                "thread_id": None,
                "app_server": {"healthy": False},
                "thread": {"status": "stopped", "raw": {}},
            },
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances/act-pm-demo/stop",
        )
        self.assertEqual(status, 202)
        self.assertEqual(payload["operation"]["action"], "stop")
        operation = self._wait_for_http_operation_status(base_url, payload["operation"]["id"], "succeeded")
        self.assertEqual(operation["result"]["instance"]["status"], "inactive")
        self.assertEqual(
            runner.calls,
            [
                ("stop", ("act-pm-demo",)),
                ("status", ("act-pm-demo",)),
            ],
        )

    def test_delete_route_returns_operation_before_launcher_finishes(self) -> None:
        runner = RecordingHostControl()
        release_delete = threading.Event()
        runner.block("delete", ("act-pm-demo",), release_delete)
        runner.set_response("delete", ("act-pm-demo",), {"actor_id": "act-pm-demo", "deleted": True})
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(
            base_url,
            method="DELETE",
            path="/api/instances/act-pm-demo",
        )
        self.assertEqual(status, 202)
        self.assertEqual(payload["operation"]["action"], "delete")
        self.assertIn(payload["operation"]["status"], {"queued", "running"})
        self.assertEqual(payload["operation"]["target"]["actor_id"], "act-pm-demo")
        operation_id = payload["operation"]["id"]
        release_delete.set()
        operation = self._wait_for_http_operation_status(base_url, operation_id, "succeeded")
        self.assertEqual(operation["result"], {"ok": True, "actor_id": "act-pm-demo"})
        self.assertEqual(runner.calls, [("delete", ("act-pm-demo",))])

    def test_delete_operation_records_command_failure_after_acceptance(self) -> None:
        runner = RecordingHostControl()
        runner.set_error(
            "delete",
            ("act-pm-demo",),
            host_control_error("LIFECYCLE_BLOCKED", "Instance delete blocked: active app-server still running.", returncode=3),
        )
        _, base_url = self._start_server(runner)
        status, payload = self._request_json(
            base_url,
            method="DELETE",
            path="/api/instances/act-pm-demo",
        )
        self.assertEqual(status, 202)
        self.assertEqual(payload["operation"]["action"], "delete")
        operation = self._wait_for_http_operation_status(base_url, payload["operation"]["id"], "failed")
        self.assertEqual(operation["error"]["code"], "LIFECYCLE_BLOCKED")
        self.assertIn("active app-server", operation["error"]["message"])

    def test_invalid_json_body_returns_structured_error(self) -> None:
        runner, base_url = self._start_server()
        status, payload = self._request_json(
            base_url,
            method="POST",
            path="/api/instances",
            raw_body=b"{bad json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(runner.calls, [])

    def test_invalid_actor_status_route_delegates_validation_to_host_control(self) -> None:
        class RejectingHostControl(RecordingHostControl):
            def status(self, actor_id: str) -> dict[str, object]:
                self.calls.append(("status", (actor_id,)))
                raise WEB_MANAGEMENT.host_control_module.HostControlError(
                    "INVALID_REQUEST",
                    "Invalid actor id.",
                    returncode=2,
                )

        host_control, base_url = self._start_server(RejectingHostControl())
        status, payload = self._request_json(
            base_url,
            method="GET",
            path="/api/instances/not-an-actor/status",
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(host_control.calls, [("status", ("not-an-actor",))])

    def test_unknown_api_route_returns_json_404(self) -> None:
        _, base_url = self._start_server()
        status, payload = self._request_json(base_url, method="GET", path="/api/unknown")
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")

    def test_static_assets_are_served(self) -> None:
        _, base_url = self._start_server()
        html_status, html = self._request_text(base_url, method="GET", path="/")
        js_status, js = self._request_text(base_url, method="GET", path="/static/app.js")
        css_status, css = self._request_text(base_url, method="GET", path="/static/styles.css")
        renderer_status, renderer = self._request_text(base_url, method="GET", path="/static/markdown-renderer.js")
        markdown_it_status, markdown_it = self._request_text(
            base_url,
            method="GET",
            path="/static/vendor/markdown-it/markdown-it.min.js",
        )
        purify_status, purify = self._request_text(
            base_url,
            method="GET",
            path="/static/vendor/dompurify/purify.min.js",
        )
        hljs_status, hljs = self._request_text(
            base_url,
            method="GET",
            path="/static/vendor/highlightjs/highlight.min.js",
        )
        hljs_css_status, hljs_css = self._request_text(
            base_url,
            method="GET",
            path="/static/vendor/highlightjs/github.min.css",
        )
        blocked_status, blocked = self._request_text(base_url, method="GET", path="/static/../../runtime.py")
        self.assertEqual(html_status, 200)
        self.assertIn("BuddySwitch Web Management", html)
        self.assertIn("webui-root", html)
        self.assertIn("Team room", html)
        self.assertIn("Track Studio", html)
        self.assertNotIn("app-shell", html)
        self.assertNotIn("workspace-page", html)
        self.assertNotIn("Actor Console", html)
        self.assertNotIn("Create Actor", html)
        self.assertEqual(js_status, 200)
        self.assertIn("buildActorConsoleUrl", js)
        self.assertIn("/api/instances", js)
        self.assertEqual(css_status, 200)
        self.assertIn(".webui-root", css)
        self.assertIn(".proto-shell", css)
        self.assertIn(".team-room", css)
        self.assertIn(".track-studio", css)
        self.assertNotIn(".app-shell", css)
        self.assertNotIn(".actor-console-grid", css)
        self.assertNotIn(".team-room-grid", css)
        self.assertEqual(renderer_status, 200)
        self.assertIn("BuddySwitchMarkdownRenderer", renderer)
        self.assertEqual(markdown_it_status, 200)
        self.assertIn("markdownit", markdown_it.lower())
        self.assertEqual(purify_status, 200)
        self.assertIn("DOMPurify", purify)
        self.assertEqual(hljs_status, 200)
        self.assertIn("hljs", hljs)
        self.assertEqual(hljs_css_status, 200)
        self.assertIn(".hljs", hljs_css)
        self.assertEqual(blocked_status, 404)
        self.assertNotIn("WebManagementService", blocked)
