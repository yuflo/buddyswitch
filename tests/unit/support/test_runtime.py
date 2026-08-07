from __future__ import annotations

import os

import buddyswitch.foundation.state.runtime as state_runtime
from tests.support.paths import REPO_ROOT
from tests.support.runtime import RuntimeTestWorkspace


def test_runtime_workspace_uses_normal_environment_bindings_outside_repo() -> None:
    original_state_root = state_runtime.STATE_ROOT
    workspace = RuntimeTestWorkspace()
    try:
        assert not workspace.root.is_relative_to(REPO_ROOT)
        assert workspace.state_root == workspace.shared_root / "state"
        assert state_runtime.ROOT == workspace.shared_root
        assert state_runtime.STATE_ROOT == workspace.state_root
        assert state_runtime.runtime_workspace_root() == workspace.root
        assert os.environ["BUDDYSWITCH_SHARED_ROOT"] == str(workspace.shared_root)
        assert os.environ["BUDDYSWITCH_STATE_ROOT"] == str(workspace.state_root)
        state_runtime.require_runtime_workspace_write_root()
    finally:
        workspace.close()

    assert state_runtime.STATE_ROOT == original_state_root
    assert not workspace.base.exists()
