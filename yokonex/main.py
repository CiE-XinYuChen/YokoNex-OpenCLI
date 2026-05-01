#!/usr/bin/env python3
"""YokoNex — Unified BLE device client.

Usage:
  yokonex server                        Start WS server (BLE bridge)
  yokonex tui                           Start terminal UI
  yokonex server --tui                  Start server + TUI together
  yokonex agent --cloud wss://...       Bridge local server to cloud relay
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import threading
import time


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(name)-20s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args():
    p = argparse.ArgumentParser(
        prog="yokonex",
        description="YokoNex BLE/WS unified device client",
    )
    p.add_argument(
        "mode",
        choices=["server", "tui", "agent"],
        nargs="?",
        default="server",
        help="Run mode (default: server)",
    )
    p.add_argument("--tui",  action="store_true", help="Launch TUI alongside server")
    p.add_argument("--host", default="127.0.0.1",  help="WS host (default: 127.0.0.1)")
    p.add_argument("--port", default=8765, type=int, help="WS port (default: 8765)")
    # agent mode
    p.add_argument("--cloud",    default="", metavar="URL",
                   help="Cloud relay WS URL (agent mode), e.g. wss://my-server:8080")
    p.add_argument("--token",    default="yokonex-agent-dev", metavar="TOKEN",
                   help="Agent auth token for cloud relay (default: yokonex-agent-dev)")
    p.add_argument("--agent-id", default="", metavar="ID",
                   help="Agent identifier shown to mobile clients (default: auto-generated)")
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    return p.parse_args()


async def _run_server(host: str, port: int) -> None:
    from yokonex.core.ws_server import WSServer
    await WSServer(host, port).start()


async def _run_agent(local_url: str, cloud_url: str, token: str, agent_id: str) -> None:
    from yokonex.core.cloud_bridge import CloudBridge
    await CloudBridge(local_url, cloud_url, token, agent_id).run()


def _run_tui(host: str, port: int) -> None:
    from yokonex.frontend.tui import run_tui
    run_tui(ws_url=f"ws://{host}:{port}")


def main() -> None:
    # Register all device implementations before anything else
    import yokonex.devices.toy.device    # noqa: F401
    import yokonex.devices.estim.device  # noqa: F401

    args = parse_args()
    _setup_logging(args.log_level)

    if args.mode == "agent":
        if not args.cloud:
            print("error: --cloud <URL> is required for agent mode")
            raise SystemExit(1)
        local_url = f"ws://{args.host}:{args.port}"
        asyncio.run(_run_agent(local_url, args.cloud, args.token, args.agent_id))

    elif args.mode == "server" and not args.tui:
        asyncio.run(_run_server(args.host, args.port))

    elif args.mode == "tui":
        _run_tui(args.host, args.port)

    elif args.mode == "server" and args.tui:
        t = threading.Thread(
            target=lambda: asyncio.run(_run_server(args.host, args.port)),
            daemon=True,
            name="yokonex-server",
        )
        t.start()
        time.sleep(0.8)
        _run_tui(args.host, args.port)


if __name__ == "__main__":
    main()
