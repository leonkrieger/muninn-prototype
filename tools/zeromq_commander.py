#!/usr/bin/env python3
"""Send commands to a Muninn suit over ZeroMQ."""

from __future__ import annotations

import argparse
import socket
import sys
import time
import tomllib
from pathlib import Path

import zmq


DEFAULT_BIND = "tcp://172.16.254.106:5556"
COMMAND_TOPIC = "commands"


def load_commands(path: Path) -> list[str]:
    with path.open("rb") as command_file:
        commands = tomllib.load(command_file).get("commands", {})
    return [str(command).strip() for command in commands if str(command).strip()]


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Send Muninn commands over ZeroMQ")
    parser.add_argument(
        "--bind",
        default=DEFAULT_BIND,
        help=f"Local ZeroMQ bind address (default: {DEFAULT_BIND})",
    )
    parser.add_argument(
        "--commands-file",
        type=Path,
        default=project_root / "config" / "commands.toml",
        help="Path to the command definitions TOML file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        commands = load_commands(args.commands_file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        print(f"Could not load commands: {error}", file=sys.stderr)
        return 1

    print(f"Available commands (bound to {args.bind}):")
    for command in commands:
        print(f"  {command}")
    print("  quit")

    context = zmq.Context()
    publisher = context.socket(zmq.PUB)
    publisher.linger = 0
    publisher.bind(args.bind)

    try:
        # ZeroMQ PUB/SUB needs a short propagation period before the first send.
        time.sleep(0.25)
        while True:
            try:
                command = input("\nCommand> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if command.lower() in {"quit", "exit"}:
                break
            if not command:
                continue

            publisher.send_multipart([COMMAND_TOPIC.encode(), command.encode()])
            print(f"Sent: {command}")
    finally:
        publisher.close()
        context.term()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
