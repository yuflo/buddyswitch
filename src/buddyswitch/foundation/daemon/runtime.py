"""Narrow host runtime facts exposed to daemon handlers."""

from __future__ import annotations

from typing import Any

from buddyswitch.foundation.daemon import contracts  # noqa: E402


class DaemonRuntime:
    def __init__(
        self,
        *,
        context: contracts.DaemonContext,
        host: contracts.DaemonHost,
    ) -> None:
        self.context = context
        self.host = host

    def parent_activity(self) -> dict[str, Any]:
        return dict(self.host.parent_activity(self.context))

    def input_actor(self, text: str) -> dict[str, Any]:
        return dict(self.host.input_actor(self.context, text))
