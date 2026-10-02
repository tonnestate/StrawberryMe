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
    if args.command == "verify":
        _print(core.verify(args.run or None))

if __name__ == "__main__":
    main()
