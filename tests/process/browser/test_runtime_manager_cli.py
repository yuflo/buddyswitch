from tests.integration.browser.cdp_lifecycle_harness import *  # noqa: F401,F403


class TestBrowserRuntimeManagerCli(unittest.TestCase):
    def test_browser_runtime_manager_cli_is_json_only_without_output_selector(self) -> None:
        actor_id = "act-browser-json-only"
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = Path(temp_root) / "instances" / actor_id
            instance_root.mkdir(parents=True)
            (instance_root / "instance.json").write_text(
                json.dumps({"actor_id": actor_id, "browser_port": None}, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )

            status_result = run_process(
                [
                    PYTHON,
                    str(BROWSER_RUNTIME_MANAGER_PATH),
                    "status",
                    "--instance-root",
                    str(instance_root),
                    "--actor-id",
                    actor_id,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(status_result.returncode, 0, msg=status_result.stderr)
            self.assertEqual(status_result.stderr, "")
            self.assertEqual(status_result.stdout.count("\n"), 1, msg=status_result.stdout)
            payload = json.loads(status_result.stdout)
            self.assertEqual(payload["ok"], True)
            self.assertEqual(payload["browser_port"], None)

            for removed_args in (["--output", "human"], ["--json"]):
                with self.subTest(removed_args=removed_args):
                    removed = run_process(
                        [
                            PYTHON,
                            str(BROWSER_RUNTIME_MANAGER_PATH),
                            "status",
                            "--instance-root",
                            str(instance_root),
                            "--actor-id",
                            actor_id,
                            *removed_args,
                        ],
                        cwd=ROOT,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(removed.returncode, 2, msg=removed.stdout + removed.stderr)
                    self.assertEqual(removed.stdout, "")
