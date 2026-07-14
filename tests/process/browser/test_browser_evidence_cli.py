from tests.integration.browser.market_evidence_harness import *  # noqa: F401,F403


class TestBrowserEvidenceCli(MarketEvidenceHarness):
    def test_browser_evidence_cli_target_type_is_artifact_only(self) -> None:
        help_result = run_process(
            [PYTHON, "scripts/browser_evidence.py", "issue", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(help_result.returncode, 0, msg=help_result.stderr)
        self.assertIn("artifact", help_result.stdout)
        self.assertNotIn("memory", help_result.stdout)

        rejected = run_process(
            [
                PYTHON,
                "scripts/browser_evidence.py",
                "issue",
                "--target-type",
                "memory",
                "--target-id",
                "mem-old",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(rejected.returncode, 2, msg=rejected.stdout + rejected.stderr)
        self.assertIn("invalid choice", rejected.stderr)
