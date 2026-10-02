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

    assess = sub.add_parser("assess")
    assess.add_argument("--path", action="append", default=[])
    assess.add_argument("--target")

    cursor = sub.add_parser("cursor")
    cursor.add_argument("target")
    cursor.add_argument("--horizon", type=int, default=1)
    cursor.add_argument("--adaptive", action="store_true")

    pre = sub.add_parser("preflight")
    pre.add_argument("--add", action="append", default=[])
    pre.add_argument("--remove", action="append", default=[])

    plan = sub.add_parser("probe-plan")
    plan.add_argument("--target")
    plan.add_argument("--path", action="append", default=[])
    plan.add_argument("--expected-runtime-edge", action="append", default=[])
    plan.add_argument("--forbidden-runtime-edge", action="append", default=[])
    plan.add_argument("--filesystem", default="TEMP_WRITE")
    plan.add_argument("--network", default="DENY")
    plan.add_argument("--process-spawn", default="DENY")
    plan.add_argument("--env", action="append", default=[])
    plan.add_argument("--max-cases", type=int, default=3)
    plan.add_argument("--max-repeats", type=int, default=3)
    plan.add_argument("--max-runtime", type=int, default=60)
    plan.add_argument("command_args", nargs=argparse.REMAINDER)

    approve = sub.add_parser("probe-approve")
    approve.add_argument("plan_id")
    approve.add_argument("--by", default="local-user")

    run = sub.add_parser("probe-run")
    run.add_argument("plan_id")

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
    if args.command == "assess":
        _print(core.assess_change(args.path or None, args.target))
    if args.command == "cursor":
        _print(core.cursor(args.target, args.horizon, adaptive=args.adaptive))
    if args.command == "preflight":
        _print(core.preflight(args.add, args.remove))
    if args.command == "probe-plan":
        command = args.command_args[1:] if args.command_args and args.command_args[0] == "--" else args.command_args
        if not command:
            parser.error("probe-plan requires a command after --")
        _print(core.probe_plan(
            command=command,
            target=args.target,
            paths=args.path or None,
            expected_runtime_edges=args.expected_runtime_edge,
            forbidden_runtime_edges=args.forbidden_runtime_edge,
            filesystem=args.filesystem,
            network=args.network,
            process_spawn=args.process_spawn,
            allowed_env_names=args.env,
            max_cases=args.max_cases,
            max_repeats=args.max_repeats,
            max_runtime_seconds=args.max_runtime,
        ))
    if args.command == "probe-approve":
        _print(core.approve_probe_plan(args.plan_id, args.by))
    if args.command == "probe-run":
        _print(core.probe_run(args.plan_id))
    if args.command == "observe":
        if not args.command_args:
            parser.error("observe requires a command after --")
        command = args.command_args[1:] if args.command_args and args.command_args[0] == "--" else args.command_args
        _print(core.observe(command, args.timeout, args.expected_runtime_edge, args.forbidden_runtime_edge))
    if args.command == "verify":
        _print(core.verify(args.run or None))


if __name__ == "__main__":
    main()
