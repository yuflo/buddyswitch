"""Machine-first CLI output helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence, TextIO


@dataclass(frozen=True)
class CliError(Exception):
    code: str
    message: str
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CliCommandResult:
    kind: str
    data: object


CliCommandHandler = Callable[[Sequence[str]], CliCommandResult]


@dataclass(frozen=True)
class CliCommandRegistration:
    name: str
    help_rows: tuple[str, ...]
    handler: CliCommandHandler


def parse_options(
    args: Sequence[str],
    *,
    allowed: tuple[str, ...],
    context: str,
) -> dict[str, str]:
    values: dict[str, str] = {}
    index = 0
    allowed_set = set(allowed)
    while index < len(args):
        option = args[index]
        if option not in allowed_set:
            raise CliError(
                "INVALID_ARGUMENT",
                f"{context} does not accept: {option}",
            )
        if option in values:
            raise CliError(
                "INVALID_ARGUMENT",
                f"{context} received {option} more than once",
            )
        if (
            index + 1 >= len(args)
            or not args[index + 1]
            or args[index + 1].startswith("-")
        ):
            raise CliError(
                "INVALID_ARGUMENT",
                f"{context} requires {option} <value>",
            )
        values[option] = args[index + 1]
        index += 2
    return values


def parse_required_options(
    args: Sequence[str],
    *,
    required: tuple[str, ...],
    context: str,
) -> dict[str, str]:
    values = parse_options(args, allowed=required, context=context)
    for option in required:
        if option not in values:
            raise CliError(
                "INVALID_ARGUMENT",
                f"{context} requires {option} <value>",
            )
    return values


def single_required_option(
    args: Sequence[str],
    option: str,
    context: str,
) -> str:
    return parse_required_options(
        args,
        required=(option,),
        context=context,
    )[option]


def optional_single_option(
    args: Sequence[str],
    option: str,
    context: str,
) -> str | None:
    return parse_options(
        args,
        allowed=(option,),
        context=context,
    ).get(option)


_EXIT_CODES = {
    "INTERNAL_ERROR": 1,
    "EXECUTION_FAILED": 1,
    "INVALID_ARGUMENT": 2,
    "UNKNOWN_COMMAND": 2,
    "NOT_FOUND": 3,
    "CONFLICT": 4,
    "PRECONDITION_FAILED": 4,
    "CONFIRMATION_REQUIRED": 4,
    "RUNTIME_UNAVAILABLE": 5,
    "RUNTIME_MISMATCH": 5,
    "TIMEOUT": 5,
}


def _canonical_error(error: CliError) -> CliError:
    if error.code in _EXIT_CODES:
        return error
    return CliError("INTERNAL_ERROR", "Unexpected internal error")


def success(kind: str, data: object) -> dict[str, object]:
    return {
        "ok": True,
        "kind": kind,
        "data": data,
    }


def failure(error: CliError) -> dict[str, object]:
    error = _canonical_error(error)
    return {
        "ok": False,
        "error": {
            "code": error.code,
            "message": error.message,
            "details": dict(error.details),
        },
    }


def exit_code(error: CliError) -> int:
    return _EXIT_CODES[_canonical_error(error).code]


def normalize_error(error: BaseException) -> CliError:
    if isinstance(error, CliError):
        return _canonical_error(error)
    return CliError("INTERNAL_ERROR", "Unexpected internal error")


def emit(payload: Mapping[str, object], stream: TextIO) -> None:
    json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
    stream.write("\n")
