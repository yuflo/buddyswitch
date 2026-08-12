"""Public entrypoint error boundaries for application Host Control assembly."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest import mock

from buddyswitch.application.build import ApplicationAssembly
from buddyswitch.application.entrypoints import cli as cli_entrypoint
from buddyswitch.application.entrypoints import web as web_entrypoint
from buddyswitch.application import host_control as application_host_control
from buddyswitch.runtime_support import env_manifest


EMPTY_APPLICATION = ApplicationAssembly(
    modules=(),
    daemon_handlers=(),
    tools=(),
    cli_commands=(),
    skills=(),
    cleanup=(),
    actor_console_sections=(),
    inbound_sources=(),
    web_routes=(),
    web_workers=(),
)


class HostControlEntrypointErrorTests(unittest.TestCase):
    def test_cli_entrypoint_supplies_one_application_input_to_foundation(self) -> None:
        host_control = mock.sentinel.host_control
        application_input = mock.sentinel.application_input
        with (
            mock.patch.object(
                cli_entrypoint,
                "activate_application",
                return_value=EMPTY_APPLICATION,
            ),
            mock.patch.object(
                cli_entrypoint,
                "assemble_host_control",
                return_value=host_control,
            ),
            mock.patch.object(
                cli_entrypoint,
                "assemble_cli_runtime",
                return_value=application_input,
            ),
            mock.patch.object(
                cli_entrypoint.cli_runtime,
                "main",
                return_value=0,
            ) as generic_main,
        ):
            status = cli_entrypoint.main()

        self.assertEqual(status, 0)
        generic_main.assert_called_once_with(
            application_input=application_input,
            host_control=host_control,
            command_registrations=EMPTY_APPLICATION.cli_commands,
        )

    def test_web_entrypoint_supplies_public_attach_module_to_foundation(self) -> None:
        host_control = mock.sentinel.host_control
        with (
            mock.patch.object(
                web_entrypoint,
                "activate_application",
                return_value=EMPTY_APPLICATION,
            ),
            mock.patch.object(
                web_entrypoint,
                "assemble_host_control",
                return_value=host_control,
            ),
            mock.patch.object(
                web_entrypoint.web_runtime,
                "main",
                return_value=0,
            ) as generic_main,
        ):
            status = web_entrypoint.main()

        self.assertEqual(status, 0)
        generic_main.assert_called_once_with(
            host_control=host_control,
            attach_cli_module=web_entrypoint.PUBLIC_ATTACH_CLI_MODULE,
        )

    def test_cli_malformed_role_catalog_uses_public_failure_envelope(self) -> None:
        stdout = io.StringIO()
        with (
            mock.patch.object(cli_entrypoint, "activate_application", return_value=EMPTY_APPLICATION),
            mock.patch.object(
                application_host_control.env_manifest,
                "load_manifest",
                side_effect=env_manifest.ManifestError("roles[0].id must be a non-empty string"),
            ),
            mock.patch.object(cli_entrypoint.cli_runtime, "main") as generic_main,
            contextlib.redirect_stdout(stdout),
        ):
            status = cli_entrypoint.main()

        self.assertEqual(status, 1)
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "ok": False,
                "error": {
                    "code": "EXECUTION_FAILED",
                    "message": "roles[0].id must be a non-empty string",
                    "details": {},
                },
            },
        )
        generic_main.assert_not_called()

    def test_web_malformed_role_catalog_uses_public_startup_error_boundary(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.object(web_entrypoint, "activate_application", return_value=EMPTY_APPLICATION),
            mock.patch.object(
                application_host_control.env_manifest,
                "load_manifest",
                side_effect=env_manifest.ManifestError("roles[0].id must be a non-empty string"),
            ),
            mock.patch.object(web_entrypoint.web_runtime, "main") as generic_main,
            contextlib.redirect_stderr(stderr),
        ):
            status = web_entrypoint.main()

        self.assertEqual(status, 1)
        self.assertEqual(stderr.getvalue(), "roles[0].id must be a non-empty string\n")
        self.assertNotIn("Traceback", stderr.getvalue())
        generic_main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
