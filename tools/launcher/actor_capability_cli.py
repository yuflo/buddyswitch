"""CLI projection for the actor capability product."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

import actor_capability  # noqa: E402


def _emit(config: actor_capability.ActorCapabilities) -> None:
    print(
        json.dumps(
            {
                "ok": True,
                "capabilities": actor_capability.describe_actor_capabilities(config),
            },
            ensure_ascii=True,
        )
    )


def _command_seed(args: argparse.Namespace) -> int:
    instance_json = Path(args.instance_json)
    path = actor_capability.seed_actor_capabilities(instance_json)
    print(json.dumps({"ok": True, "path": str(path)}, ensure_ascii=True))
    return 0


def _command_get(args: argparse.Namespace) -> int:
    _emit(actor_capability.load_actor_capabilities(Path(args.instance_json)))
    return 0


def _command_replace(args: argparse.Namespace) -> int:
    config = actor_capability.replace_actor_capabilities(
        Path(args.instance_json),
        parent_level=args.parent,
        side_level=args.side,
    )
    _emit(config)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed = subparsers.add_parser("seed")
    seed.add_argument("--instance-json", required=True)
    seed.set_defaults(func=_command_seed)

    get = subparsers.add_parser("get")
    get.add_argument("--instance-json", required=True)
    get.set_defaults(func=_command_get)

    replace = subparsers.add_parser("replace")
    replace.add_argument("--instance-json", required=True)
    replace.add_argument("--parent", required=True)
    replace.add_argument("--side", required=True)
    replace.set_defaults(func=_command_replace)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except actor_capability.ActorCapabilityError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
