#!/usr/bin/env python3
"""Launcher-owned input wrapper selection and composition."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

from input_wrappers import raw as raw_wrapper
from input_wrappers import task_tui as task_tui_wrapper


class InputWrapperError(RuntimeError):
    """Base launcher input wrapper error."""


class InputWrapperSelectionError(InputWrapperError):
    """Raised when the requested wrapper name is invalid."""


class InputWrapperCompositionError(InputWrapperError):
    """Raised when a valid wrapper cannot compose text."""


def compose_input_text(*, wrapper_name: str, raw_text: str, instance_json: Path) -> str:
    if wrapper_name == "raw":
        return raw_wrapper.compose(raw_text=raw_text, instance_json=instance_json)
    if wrapper_name == "task-tui":
        try:
            return task_tui_wrapper.compose(raw_text=raw_text, instance_json=instance_json)
        except task_tui_wrapper.TaskTuiInputWrapperError as exc:
            raise InputWrapperCompositionError(str(exc)) from exc
    raise InputWrapperSelectionError(f"unknown input wrapper: {wrapper_name}")


def _command_compose(args: argparse.Namespace) -> int:
    text = compose_input_text(
        wrapper_name=args.wrapper,
        raw_text=args.text,
        instance_json=_resolve_instance_json(),
    )
    sys.stdout.write(text)
    return 0


def _resolve_instance_json() -> Path:
    instance_json = os.environ.get("BUDDYSWITCH_INSTANCE_JSON", "").strip()
    if not instance_json:
        raise InputWrapperCompositionError("BUDDYSWITCH_INSTANCE_JSON is required for launcher input wrapper composition")
    return Path(instance_json)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compose_parser = subparsers.add_parser("compose")
    compose_parser.add_argument("--wrapper", required=True)
    compose_parser.add_argument("--text", required=True)
    compose_parser.set_defaults(func=_command_compose)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except InputWrapperSelectionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except InputWrapperError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
