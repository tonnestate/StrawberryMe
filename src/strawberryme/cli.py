from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import StrawberryCore


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(prog="strawberry")
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")

    cursor = sub.add_parser("cursor")
    cursor.add_argument("target")
    cursor.add_argument("--horizon", type=int, default=1)

    pre = sub.add_parser("preflight")
    pre.add_argument("--add", action="append", default=[])
    pre.add_argument("--remove", action="append", default=[])

    observe = sub.add_parser("observe")
    observe.add_argument("--expected-runtime-edge", action="append", default=[])
    observe.add_argument("--forbidden-runtime-edge", action="append", default=[])
    observe.add_argument("--timeout", type=int, default=30)
    observe.add_argument("command_args", nargs=argparse.REMAINDER)

    verify = sub.add_parser("verify")
    verify.add_argument("--run", nargs=argparse.REMAINDER)

    args = parser.parse_args()
    core = StrawberryCore(Path(args.root))
    if args.command == "status":
        _print(core.status())
    if args.command == "cursor":
        _print(core.cursor(args.target, args.horizon))
    if args.command == "preflight":
        _print(core.preflight(args.add, args.remove))
    if args.command == "observe":
        if not args.command_args:
            parser.error("observe requires a command after --")
        command = args.command_args[1:] if args.command_args and args.command_args[0] == "--" else args.command_args
        _print(core.observe(command, args.timeout, args.expected_runtime_edge, args.forbidden_runtime_edge))
    if args.command == "verify":
        _print(core.verify(args.run or None))


if __name__ == "__main__":
    main()
