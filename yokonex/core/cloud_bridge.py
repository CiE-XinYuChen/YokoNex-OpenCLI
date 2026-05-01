"""cloud_bridge.py — Relay between local yokonex WS server and cloud relay server.

Usage (via CLI):
    yokonex agent --cloud wss://your-server:8080 --token <AGENT_TOKEN> --agent-id home-pc

How it works:
    1. Connects to the local yokonex WS server (ws://127.0.0.1:8765).
    2. Connects to the cloud relay server and registers as an agent.
    3. Forwards commands from cloud clients → local server (strips _src field).
    4. Forwards responses and events from local server → cloud (pass-through).

When the yokonex whl is upgraded with new device types or commands they are
automatically supported — this bridge is a transparent proxy with no device logic.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid

import websockets

log = logging.getLogger("yokonex.cloud_bridge")


class CloudBridge:
    def __init__(
        self,
        local_url:  str,
        cloud_url:  str,
        token:      str,
        agent_id:   str = "",
    ) -> None:
        self.local_url = local_url
        self.cloud_url = cloud_url
        self.token     = token
        self.agent_id  = agent_id or str(uuid.uuid4())[:8]

    # ── Public ────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Run bridge forever, reconnecting on any error."""
        log.info("CloudBridge agent_id=%s", self.agent_id)
        while True:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("Bridge lost connection (%s), retry in 5 s", exc)
                await asyncio.sleep(5)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _run_once(self) -> None:
        log.info("Connecting local  → %s", self.local_url)
        async with websockets.connect(self.local_url) as local_ws:
            log.info("Connecting cloud  → %s", self.cloud_url)
            async with websockets.connect(self.cloud_url) as cloud_ws:
                # Register as agent
                await cloud_ws.send(json.dumps({
                    "type":     "agent_hello",
                    "token":    self.token,
                    "agent_id": self.agent_id,
                    "meta":     {"local_url": self.local_url},
                }))
                raw = await cloud_ws.recv()
                hello = json.loads(raw)
                if not hello.get("ok"):
                    raise RuntimeError(f"Cloud auth failed: {hello}")
                log.info("Registered as agent '%s'", hello.get("agent_id", self.agent_id))

                await asyncio.gather(
                    self._cloud_to_local(cloud_ws, local_ws),
                    self._local_to_cloud(local_ws, cloud_ws),
                )

    async def _cloud_to_local(self, cloud_ws, local_ws) -> None:
        """Forward commands from cloud clients to local yokonex server."""
        async for raw in cloud_ws:
            try:
                msg = json.loads(raw)
                # Strip routing metadata added by the cloud server
                msg.pop("_src", None)
                await local_ws.send(json.dumps(msg))
                log.debug("cloud→local  %s", raw[:120])
            except Exception as exc:
                log.error("cloud→local error: %s", exc)

    async def _local_to_cloud(self, local_ws, cloud_ws) -> None:
        """Forward responses and events from local server to cloud."""
        async for raw in local_ws:
            try:
                await cloud_ws.send(raw)
                log.debug("local→cloud  %s", raw[:120])
            except Exception as exc:
                log.error("local→cloud error: %s", exc)
