import ast

from tests.integration.web.management_harness import *  # noqa: F401,F403


class WebManagementProductApiTests(RuntimeWorkspaceTestCase):
    def _use_capability_shared_root(self) -> Path:
        from buddyswitch.env.repos import runtime_files

        shared_root = self.runtime_root / "shared-root"
        state_root = shared_root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        updates = {
            "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
            "BUDDYSWITCH_STATE_ROOT": str(state_root),
            "BUDDYSWITCH_WORKSPACE_DIR": str(shared_root),
        }
        original = {key: os.environ.get(key) for key in updates}
        self.addCleanup(runtime_files.refresh_runtime_roots_from_env)
        for key, value in original.items():
            self.addCleanup(_restore_env_value, key, value)
        os.environ.update(updates)
        runtime_files.refresh_runtime_roots_from_env()
        return shared_root

    def _service(self, host_control: RecordingHostControl | None = None) -> WEB_MANAGEMENT.WebManagementService:
        return WEB_MANAGEMENT.WebManagementService(
            host_control=host_control or RecordingHostControl(),
            web_routes=WEB_ROUTES,
            actor_console_sections=ACTOR_CONSOLE_SECTIONS,
        )

    @staticmethod
    def _instance_list_payload() -> dict[str, object]:
        return {
            "instances": [
                {
                    "actor_id": "act-pm-demo",
                    "role": "pm",
                    "status": "active",
                    "app_server_health": "healthy",
                    "thread_id": "thread-main",
                    "browser_port": 9222,
                    "updated_at": "2026-06-26T10:00:00Z",
                    "workspace_dir": "/tmp/buddyswitch/instances/act-pm-demo/workspace",
                    "last_failure": None,
                },
                {
                    "actor_id": "act-dev-demo",
                    "role": "dev",
                    "status": "inactive",
                    "app_server_health": "unhealthy",
                    "thread_id": None,
                    "browser_port": None,
                    "updated_at": "2026-06-26T10:05:00Z",
                    "workspace_dir": "/tmp/buddyswitch/instances/act-dev-demo/workspace",
                    "last_failure": None,
                },
            ]
        }

    @staticmethod
    def _instance_status_payload() -> dict[str, object]:
        return {
            "actor_id": "act-pm-demo",
            "role": "pm",
            "status": "active",
            "workspace_dir": "/tmp/buddyswitch/instances/act-pm-demo/workspace",
            "browser_port": 9222,
            "updated_at": "2026-06-26T10:00:00Z",
            "thread_id": "thread-main",
            "app_server_health": "healthy",
            "app_server": {"healthy": True},
            "thread": {"status": "idle", "raw": {}},
        }

    def _seed_track_pages(self) -> None:
        from buddyswitch.modules.track.private.state import (
            track_comments as track_comment_repo,
        )
        from buddyswitch.modules.track.private.state import tracks as track_repo

        actor = {"role_id": "pm", "actor_id": "act-pm-demo"}
        actor_id = actor["actor_id"]
        track_repo.save_track(
            {
                "id": "track-alpha",
                "title": "Actor console",
                "outcome": "Ship actor-centered Web management.",
                "owner_identity_id": actor_id,
                "state": "active",
                "now": {"next": "Implement Web DTOs.", "blocker": None},
                "acceptance_criteria": ["Actor is the primary object."],
                "non_goals": ["Do not add lower actor.tasks API."],
                "artifact_relations": [
                    {
                        "type": "artifact",
                        "relation_id": "rel-material",
                        "artifact_id": "artifact-material",
                        "role": "material",
                        "label": "Brief",
                        "template": "markdown",
                        "from_identity_id": actor_id,
                        "summary": "Source brief.",
                        "current": True,
                        "created_at": "2026-06-26T09:00:00Z",
                    },
                    {
                        "type": "artifact",
                        "relation_id": "rel-proof",
                        "artifact_id": "artifact-proof",
                        "role": "proof",
                        "label": "Plan",
                        "template": "markdown",
                        "from_identity_id": actor_id,
                        "summary": "Implementation plan.",
                        "current": True,
                        "created_at": "2026-06-26T09:10:00Z",
                    },
                ],
                "updates": [
                    {
                        "id": "upd-plan",
                        "by_identity_id": actor_id,
                        "summary": "Phase two boundary confirmed.",
                        "kind": "decision",
                        "refs": [{"type": "artifact", "id": "artifact-proof"}],
                        "created_at": "2026-06-26T09:15:00Z",
                    }
                ],
                "created_at": "2026-06-26T08:00:00Z",
                "updated_at": "2026-06-26T10:00:00Z",
                "archived_at": None,
            }
        )
        track_repo.save_track(
            {
                "id": "track-archived",
                "title": "Archived work",
                "outcome": "Do not show archived Track pages.",
                "owner_identity_id": actor_id,
                "state": "active",
                "now": {"next": "Archived.", "blocker": None},
                "acceptance_criteria": [],
                "non_goals": [],
                "artifact_relations": [],
                "updates": [],
                "created_at": "2026-06-25T08:00:00Z",
                "updated_at": "2026-06-25T10:00:00Z",
                "archived_at": "2026-06-25T11:00:00Z",
            }
        )
        track_comment_repo.save_track_comment(
            {
                "id": "comment-root",
                "track_id": "track-alpha",
                "thread_id": "thread-open",
                "by_identity_id": "act-dev-demo",
                "content": "Need Track detail to include comments.",
                "reply_to": None,
                "mentioned_identity_ids": [actor_id],
                "status": "open",
                "created_at": "2026-06-26T10:01:00Z",
                "resolved_by_identity_id": None,
                "resolved_at": None,
                "resolution_summary": None,
            }
        )
        track_comment_repo.save_track_comment(
            {
                "id": "comment-reply",
                "track_id": "track-alpha",
                "thread_id": "thread-open",
                "by_identity_id": actor_id,
                "content": "Comments stay inside Track detail for phase two.",
                "reply_to": "comment-root",
                "mentioned_identity_ids": [],
                "status": "open",
                "created_at": "2026-06-26T10:02:00Z",
                "resolved_by_identity_id": None,
                "resolved_at": None,
                "resolution_summary": None,
            }
        )
        track_comment_repo.save_track_comment(
            {
                "id": "comment-resolved",
                "track_id": "track-alpha",
                "thread_id": "thread-resolved",
                "by_identity_id": actor_id,
                "content": "Resolved discussion.",
                "reply_to": None,
                "mentioned_identity_ids": [],
                "status": "resolved",
                "created_at": "2026-06-26T10:03:00Z",
                "resolved_by_identity_id": actor_id,
                "resolved_at": "2026-06-26T10:04:00Z",
                "resolution_summary": "Closed.",
            }
        )

    def test_actor_roster_api_projects_instance_list_as_actor_rows(self) -> None:
        runner = RecordingHostControl()
        runner.list_instances_response = self._instance_list_payload()["instances"]
        service = self._service(runner)

        status, payload = service.handle_api("GET", "/api/actors", b"")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual([row["actor_id"] for row in payload["actors"]], ["act-pm-demo", "act-dev-demo"])
        self.assertEqual(payload["actors"][0]["runtime"]["status"], "active")
        self.assertEqual(payload["actors"][0]["runtime"]["app_server_health"], "healthy")
        self.assertEqual(payload["actors"][0]["lifecycle_state"], "active")
        self.assertEqual(payload["actors"][1]["runtime"]["status"], "inactive")
        self.assertEqual(payload["actors"][1]["lifecycle_state"], "stopped")
        self.assertEqual(runner.calls, [("list_instances", (None,))])

    def test_actor_roster_merges_start_operation_and_published_instance_into_one_starting_row(self) -> None:
        runner = RecordingHostControl()
        release_start = threading.Event()
        actor_id = "act-dev-demo"
        runner.roles_response = [{"id": "dev", "label": "Dev", "scope": "product"}]
        runner.list_instances_response = [dict(failed_status(actor_id, role="dev"), last_failure=None)]
        runner.block("start", ("dev", actor_id), release_start)
        runner.set_response("start", ("dev", actor_id), {"actor_id": actor_id})
        runner.set_response("status", (actor_id,), active_status(actor_id, "thread-dev", "idle"))
        service = self._service(runner)

        _, start_payload = service.handle_api("POST", "/api/instances", b'{"role":"dev"}')
        try:
            wait_for_operation_status(service, start_payload["operation"]["id"], "running")
            status, payload = service.handle_api("GET", "/api/actors", b"")

            self.assertEqual(status, 200)
            self.assertEqual(len(payload["actors"]), 1)
            self.assertEqual(payload["actors"][0]["actor_id"], actor_id)
            self.assertEqual(payload["actors"][0]["lifecycle_state"], "starting")
            self.assertEqual(payload["actors"][0]["lifecycle_operation"]["id"], start_payload["operation"]["id"])
        finally:
            release_start.set()
        wait_for_operation_status(service, start_payload["operation"]["id"], "succeeded")

    def test_actor_roster_correlates_retry_across_previous_and_replacement_ids(self) -> None:
        runner = RecordingHostControl()
        release_retry = threading.Event()
        previous_actor_id = "act-pm-failed"
        replacement_actor_id = "act-pm-replacement"
        previous = failed_status(previous_actor_id)
        replacement = failed_status(replacement_actor_id)
        runner.list_instances_response = [previous]
        runner.set_response(
            "prepare_retry",
            (previous_actor_id,),
            {
                "actor_id": previous_actor_id,
                "replacement_actor_id": replacement_actor_id,
                "role": "pm",
            },
        )
        runner.block("retry", (previous_actor_id, replacement_actor_id), release_retry)
        runner.set_response(
            "retry",
            (previous_actor_id, replacement_actor_id),
            {"previous_actor_id": previous_actor_id, "actor_id": replacement_actor_id, "role": "pm"},
        )
        runner.set_response(
            "status",
            (replacement_actor_id,),
            active_status(replacement_actor_id, "thread-replacement", "idle"),
        )
        service = self._service(runner)

        _, retry_payload = service.handle_api("POST", f"/api/instances/{previous_actor_id}/retry", b"")
        try:
            wait_for_operation_status(service, retry_payload["operation"]["id"], "running")
            _, before = service.handle_api("GET", "/api/actors", b"")
            self.assertEqual(len(before["actors"]), 1)
            self.assertEqual(before["actors"][0]["actor_id"], previous_actor_id)
            self.assertEqual(before["actors"][0]["replacement_actor_id"], replacement_actor_id)
            self.assertEqual(before["actors"][0]["lifecycle_state"], "retrying")

            runner.list_instances_response = [previous, replacement]
            _, after = service.handle_api("GET", "/api/actors", b"")
            self.assertEqual(len(after["actors"]), 1)
            self.assertEqual(after["actors"][0]["actor_id"], replacement_actor_id)
            self.assertEqual(after["actors"][0]["previous_actor_id"], previous_actor_id)
            self.assertEqual(after["actors"][0]["lifecycle_state"], "retrying")
        finally:
            release_retry.set()
        wait_for_operation_status(service, retry_payload["operation"]["id"], "succeeded")

    def test_actor_roster_projects_published_start_failure_as_start_failed(self) -> None:
        runner = RecordingHostControl()
        runner.list_instances_response = [failed_status("act-pm-failed")]
        service = self._service(runner)

        _, payload = service.handle_api("GET", "/api/actors", b"")

        self.assertEqual(len(payload["actors"]), 1)
        self.assertEqual(payload["actors"][0]["lifecycle_state"], "start_failed")
        self.assertEqual(payload["actors"][0]["last_failure"]["phase"], "daemon_start")

    def test_actor_capabilities_get_api_returns_creation_default_dto(self) -> None:
        shared_root = self._use_capability_shared_root()
        write_web_capability_instance(shared_root)
        service = self._service()

        status, payload = service.handle_api("GET", "/api/actors/act-pm-demo/capabilities", b"")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["actor_id"], "act-pm-demo")
        self.assertEqual(payload["capabilities"]["parent"]["level"], "balanced")
        self.assertEqual(payload["capabilities"]["side"]["level"], "fast")
        self.assertEqual([row["id"] for row in payload["capabilities"]["levels"]], ["fast", "balanced", "deep", "maximum"])

    def test_actor_capabilities_put_replaces_snapshot_and_runtime_uses_same_core(self) -> None:
        shared_root = self._use_capability_shared_root()
        instance_json = write_web_capability_instance(shared_root)
        service = self._service()

        put_status, put_payload = service.handle_api(
            "PUT",
            "/api/actors/act-pm-demo/capabilities",
            b'{"parent":"deep","side":"maximum"}',
        )
        get_status, get_payload = service.handle_api("GET", "/api/actors/act-pm-demo/capabilities", b"")
        parent = actor_capability.resolve_parent_capability(instance_json)
        side = actor_capability.resolve_side_capability(instance_json)

        self.assertEqual(put_status, 200)
        self.assertEqual(get_status, 200)
        self.assertEqual(put_payload["capabilities"], get_payload["capabilities"])
        self.assertEqual((parent.level, parent.model, parent.effort), ("deep", "gpt-5.6-sol", "xhigh"))
        self.assertEqual((side.level, side.model, side.effort), ("maximum", "gpt-5.6-sol", "max"))

    def test_actor_capabilities_host_control_set_is_readable_from_web_api(self) -> None:
        shared_root = self._use_capability_shared_root()
        write_web_capability_instance(shared_root)

        host_payload = WEB_MANAGEMENT.host_control_module.HostControl().capabilities_set(
            "act-pm-demo", parent="deep", side="maximum"
        )
        service = self._service()
        status, payload = service.handle_api("GET", "/api/actors/act-pm-demo/capabilities", b"")

        self.assertTrue(host_payload["ok"])
        self.assertEqual(host_payload["capabilities"]["parent"]["level"], "deep")
        self.assertEqual(host_payload["capabilities"]["side"]["level"], "maximum")
        self.assertEqual(status, 200)
        self.assertEqual(payload["capabilities"]["parent"]["level"], "deep")
        self.assertEqual(payload["capabilities"]["side"]["level"], "maximum")

    def test_actor_capabilities_web_put_is_readable_from_host_control_get(self) -> None:
        shared_root = self._use_capability_shared_root()
        write_web_capability_instance(shared_root)
        service = self._service()

        status, payload = service.handle_api(
            "PUT",
            "/api/actors/act-pm-demo/capabilities",
            b'{"parent":"deep","side":"maximum"}',
        )
        host_payload = WEB_MANAGEMENT.host_control_module.HostControl().capabilities_get("act-pm-demo")

        self.assertEqual(status, 200)
        self.assertTrue(host_payload["ok"])
        self.assertEqual(host_payload["actor_id"], "act-pm-demo")
        self.assertEqual(host_payload["capabilities"], payload["capabilities"])

    def test_actor_capabilities_api_rejects_invalid_actor_ids_and_missing_instances(self) -> None:
        shared_root = self._use_capability_shared_root()
        shared_root.mkdir(parents=True, exist_ok=True)
        service = self._service()

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as invalid_actor:
            service.handle_api("GET", "/api/actors/not-an-actor/capabilities", b"")
        with self.assertRaises(WEB_MANAGEMENT.HttpError) as missing_actor:
            service.handle_api("GET", "/api/actors/act-pm-missing/capabilities", b"")

        self.assertEqual(invalid_actor.exception.status, 400)
        self.assertEqual(invalid_actor.exception.code, "INVALID_REQUEST")
        self.assertEqual(missing_actor.exception.status, 404)
        self.assertEqual(missing_actor.exception.code, "NOT_FOUND")

    def test_actor_capabilities_put_invalid_payload_is_400_and_preserves_file(self) -> None:
        shared_root = self._use_capability_shared_root()
        instance_json = write_web_capability_instance(shared_root)
        path = instance_json.parent / "capability-config.json"
        before = path.read_text(encoding="utf-8")
        service = self._service()

        for body in (
            b'{"parent":"custom","side":"fast"}',
            b'{"parent":"balanced","side":"fast","model":"gpt-5.6-sol"}',
            b'{"parent":"balanced"}',
        ):
            with self.subTest(body=body), self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                service.handle_api("PUT", "/api/actors/act-pm-demo/capabilities", body)
            self.assertEqual(raised.exception.status, 400)
            self.assertEqual(raised.exception.code, "INVALID_REQUEST")
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_actor_capabilities_get_invalid_existing_config_is_409(self) -> None:
        shared_root = self._use_capability_shared_root()
        instance_json = write_web_capability_instance(shared_root)
        (instance_json.parent / "capability-config.json").write_text("{bad json\n", encoding="utf-8")
        service = self._service()

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("GET", "/api/actors/act-pm-demo/capabilities", b"")

        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(raised.exception.code, "CAPABILITY_CONFIG_INVALID")

    def test_actor_capabilities_put_write_failure_is_502(self) -> None:
        shared_root = self._use_capability_shared_root()
        instance_json = write_web_capability_instance(shared_root)
        service = self._service()

        with mock.patch.object(
            WEB_MANAGEMENT.host_control_module.actor_capability,
            "replace_actor_capabilities",
            side_effect=actor_capability.ActorCapabilityError(
                f"{instance_json.parent / 'capability-config.json'}: failed to write capability config: denied"
            ),
        ):
            with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                service.handle_api(
                    "PUT",
                    "/api/actors/act-pm-demo/capabilities",
                    b'{"parent":"balanced","side":"fast"}',
                )

        self.assertEqual(raised.exception.status, 502)
        self.assertEqual(raised.exception.code, "CAPABILITY_CONFIG_WRITE_FAILED")

    def test_web_im_send_resolves_actor_route_from_instance_list_not_identity_id_text(self) -> None:
        target_identity_id = "act-web-identity-route"
        save_test_actor_identity_profile(actor_id=target_identity_id, role_id="market")
        runner = RecordingHostControl()
        runner.list_instances_response = [
            {
                "actor_id": target_identity_id,
                "role": "market",
                "status": "active",
                "app_server_health": "healthy",
                "thread_id": "thread-market",
                "browser_port": None,
                "updated_at": "2026-06-26T10:10:00Z",
                "workspace_dir": "/tmp/buddyswitch/instances/act-web-identity-route/workspace",
            }
        ]
        service = self._service(runner)

        with mock.patch.object(
            communication_web.daemon_client,
            "check_reachability",
            return_value={
                "reachability_status": "online",
                "target_identity_id": target_identity_id,
                "record": {"identity_id": target_identity_id},
            },
        ), mock.patch.object(
            communication_web.im_actor_delivery,
            "deliver",
            return_value={"actor_handling_status": "submitted", "runtime_target": "parent", "error": None},
        ) as deliver_im_actor:
            status, payload = service.handle_api(
                "POST",
                "/api/im/messages",
                json.dumps({"target_identity_id": target_identity_id, "content": "ping"}).encode("utf-8"),
                {},
            )

        self.assertEqual(status, 200, msg=payload)
        self.assertEqual(payload["actor_handling_status"], "submitted")
        self.assertNotIn("wake_" + "status", payload)
        deliver_im_actor.assert_called_once()
        self.assertEqual(deliver_im_actor.call_args.args[0]["target_identity_id"], target_identity_id)
        self.assertNotIn("target_" + "role_id", deliver_im_actor.call_args.args[0])

    def test_actor_console_api_composes_runtime_task_sys_track_and_im_projection(self) -> None:
        from tests.support import task_fixtures

        shared_root = self._use_capability_shared_root()
        write_web_capability_instance(
            shared_root,
            capability_config={
                "schema_version": 1,
                "catalog_version": 1,
                "parent": {"level": "deep", "model": "gpt-5.6-sol", "effort": "xhigh"},
                "side": {"level": "maximum", "model": "gpt-5.6-sol", "effort": "max"},
            },
        )
        self._seed_track_pages()
        runner = RecordingHostControl()
        runner.set_response("status", ("act-pm-demo",), self._instance_status_payload())
        service = self._service(runner)
        terminal_task_ids = []
        for index in range(6):
            objective = f"Deliver Web console terminal fixture {index} through its native Goal."
            terminal_result = task_fixtures.create_task(
                actor_target={"actor_id": "act-pm-demo", "role_id": "pm"},
                demand_ref={
                    "demand_id": f"demand-web-console-terminal-{index}",
                    "basis_revision": 1,
                    "demand_ref": f"dref-web-console-terminal-{index}",
                },
                objective=objective,
                selection_reason="Exercise the management console recent Task projection.",
            )
            terminal_task_ids.append(terminal_result["task_id"])
            if index % 2:
                task_fixtures.record_task_cancel(terminal_result["task_id"], "Fixture cancellation.")
            else:
                goal = {
                    "threadId": "thread-main",
                    "objective": objective,
                    "status": "complete",
                    "tokenBudget": None,
                    "tokensUsed": 10 + index,
                    "timeUsedSeconds": 2,
                    "createdAt": 100 + index,
                    "updatedAt": 200 + index,
                }
                task_fixtures.bind_goal(terminal_result["task_id"], goal)
                task_fixtures.record_goal_complete(terminal_result["task_id"], goal)

        active_objective = "Deliver the current Web console fixture through its native Goal."
        task_result = task_fixtures.create_task(
            actor_target={"actor_id": "act-pm-demo", "role_id": "pm"},
            demand_ref={
                "demand_id": "demand-web-console",
                "basis_revision": 1,
                "demand_ref": "dref-web-console",
            },
            objective=active_objective,
            selection_reason="The Task slot is empty and this Demand is the current priority.",
        )
        task_fixtures.bind_goal(
            task_result["task_id"],
            {
                "threadId": "thread-main",
                "objective": active_objective,
                "status": "active",
                "tokenBudget": None,
                "tokensUsed": 3,
                "timeUsedSeconds": 1,
                "createdAt": 300,
                "updatedAt": 301,
            },
        )

        source = WEB_MANAGEMENT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(WEB_MANAGEMENT_PATH))
        task_private_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                task_private_imports.extend(
                    alias.name
                    for alias in node.names
                    if alias.name.startswith("buddyswitch.modules.task.private")
                )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("buddyswitch.modules.task.private"):
                    task_private_imports.append(module)
        task_lifecycle_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and node.id
            in {
                "TASK_STATUSES",
                "ACTIVE_TASK_STATUSES",
                "TERMINAL_TASK_STATUSES",
            }
        }
        task_terminal_literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and node.value in {"completed", "canceled"}
        }
        self.assertEqual(task_private_imports, [])
        self.assertEqual(task_lifecycle_names, set())
        self.assertEqual(task_terminal_literals, set())
        task_read_module = task_fixtures.task_read_model()
        with mock.patch.object(
            task_read_module,
            "actor_external_task_projection",
            wraps=task_read_module.actor_external_task_projection,
        ) as actor_projection:
            status, payload = service.handle_api("GET", "/api/actors/act-pm-demo/console", b"")

        self.assertEqual(status, 200)
        actor_projection.assert_called_once()
        projection_profile = actor_projection.call_args.kwargs["actor_profile"]
        self.assertEqual(projection_profile.identity.id, "act-pm-demo")
        self.assertEqual(projection_profile.role_id, "pm")
        console = payload["console"]
        self.assertEqual(console["actor"], {"actor_id": "act-pm-demo", "role": "pm"})
        self.assertEqual(console["runtime"]["thread_status"], "idle")
        self.assertEqual(console["task_sys"]["active_count"], 1)
        self.assertEqual(console["task_sys"]["terminal_count"], 6)
        self.assertNotIn("recoverable_count", console["task_sys"])
        self.assertNotIn("recoverable_tasks", console["task_sys"])
        self.assertEqual(len(console["task_sys"]["terminal_tasks"]), 5)
        expected_terminal_tasks = task_read_module.actor_external_task_projection(
            actor_profile=projection_profile
        )["terminal_tasks"]
        self.assertEqual(console["task_sys"]["terminal_tasks"], expected_terminal_tasks[:5])
        self.assertEqual(
            {row["task_id"] for row in expected_terminal_tasks},
            set(terminal_task_ids),
        )
        external_task_keys = (
            "task_id",
            "demand_ref",
            "objective",
            "selection",
            "goal_binding",
            "status",
            "result",
            "actor",
            "updated_at",
        )
        active_task = next(
            row for row in console["task_sys"]["active_tasks"] if row["task_id"] == task_result["task_id"]
        )
        self.assertEqual(tuple(active_task.keys()), external_task_keys)
        self.assertEqual(active_task["task_id"], task_result["task_id"])
        self.assertEqual(active_task["objective"], active_objective)
        self.assertEqual(active_task["status"], "active")
        self.assertEqual(active_task["goal_binding"]["thread_id"], "thread-main")
        self.assertEqual(active_task["actor"], {"actor_id": "act-pm-demo", "role_id": "pm"})
        for row in (active_task, *console["task_sys"]["terminal_tasks"]):
            self.assertEqual(tuple(row.keys()), external_task_keys)
            self.assertNotIn("source_type", row)
            self.assertNotIn("execution", row)
            self.assertNotIn("events", row)
        self.assertEqual(console["im"]["target"]["identity"], {"id": "act-pm-demo", "type": "actor"})
        self.assertEqual(console["im"]["target"]["identity_id"], "act-pm-demo")
        self.assertEqual(console["im"]["target"]["role_id"], "pm")
        self.assertNotIn("actor_address", console["im"]["target"])
        self.assertEqual([row["id"] for row in console["tracks"]["items"]], ["track-alpha"])
        self.assertEqual(console["capabilities"]["parent"]["level"], "deep")
        self.assertEqual(console["capabilities"]["side"]["level"], "maximum")
        self.assertNotIn("model_config", console)

    def test_actor_console_api_rejects_invalid_actor_ids(self) -> None:
        class RejectingHostControl(RecordingHostControl):
            def status(self, actor_id: str) -> dict[str, object]:
                self.calls.append(("status", (actor_id,)))
                raise WEB_MANAGEMENT.host_control_module.HostControlError(
                    "INVALID_REQUEST",
                    "Invalid actor id.",
                    returncode=2,
                )

        host_control = RejectingHostControl()
        service = WEB_MANAGEMENT.WebManagementService(host_control=host_control)

        with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
            service.handle_api("GET", "/api/actors/not-an-actor/console", b"")

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(raised.exception.code, "INVALID_REQUEST")
        self.assertEqual(host_control.calls, [("status", ("not-an-actor",))])

    def test_track_list_api_returns_non_archived_track_summaries(self) -> None:
        self._seed_track_pages()
        service = self._service()

        status, payload = service.handle_api("GET", "/api/tracks", b"")

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual([row["id"] for row in payload["tracks"]], ["track-alpha"])
        summary = payload["tracks"][0]
        self.assertEqual(
            tuple(summary.keys()),
            (
                "id",
                "title",
                "outcome",
                "owner_identity_id",
                "state",
                "now",
                "acceptance_criteria",
                "non_goals",
                "updated_at",
                "comment_summary",
            ),
        )
        self.assertEqual(summary["title"], "Actor console")
        self.assertEqual(summary["comment_summary"]["comment_count"], 3)
        self.assertEqual(summary["comment_summary"]["open_thread_count"], 1)

    def test_track_detail_api_includes_materials_proofs_updates_and_comment_threads(self) -> None:
        self._seed_track_pages()
        service = self._service()

        status, payload = service.handle_api("GET", "/api/tracks/track-alpha", b"")

        self.assertEqual(status, 200)
        track = payload["track"]
        self.assertEqual(
            tuple(track.keys()),
            (
                "id",
                "title",
                "outcome",
                "owner_identity_id",
                "state",
                "now",
                "acceptance_criteria",
                "non_goals",
                "updated_at",
                "comment_summary",
                "materials",
                "proofs",
                "updates",
                "comment_threads",
            ),
        )
        self.assertEqual(track["id"], "track-alpha")
        self.assertEqual([row["artifact_id"] for row in track["materials"]], ["artifact-material"])
        self.assertEqual([row["artifact_id"] for row in track["proofs"]], ["artifact-proof"])
        self.assertEqual([row["id"] for row in track["updates"]], ["upd-plan"])
        self.assertEqual(track["comment_summary"]["comment_count"], 3)
        self.assertEqual(track["comment_summary"]["open_thread_count"], 1)
        self.assertEqual(track["comment_summary"]["resolved_thread_count"], 1)
        self.assertEqual([row["thread_id"] for row in track["comment_threads"]], ["thread-resolved", "thread-open"])
        open_thread = next(row for row in track["comment_threads"] if row["thread_id"] == "thread-open")
        self.assertEqual(open_thread["status"], "open")
        self.assertEqual(open_thread["comment_count"], 2)
        self.assertEqual(open_thread["latest_comment_id"], "comment-reply")
        self.assertEqual(open_thread["latest_comment_preview"], "Comments stay inside Track detail for phase two.")

    def test_track_detail_api_returns_not_found_for_missing_or_archived_tracks(self) -> None:
        self._seed_track_pages()
        service = self._service()

        for track_id in ("track-missing", "track-archived"):
            with self.subTest(track_id=track_id):
                with self.assertRaises(WEB_MANAGEMENT.HttpError) as raised:
                    service.handle_api("GET", f"/api/tracks/{track_id}", b"")
                self.assertEqual(raised.exception.status, 404)
                self.assertEqual(raised.exception.code, "NOT_FOUND")
