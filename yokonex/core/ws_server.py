"""WebSocket server — bridges WS clients and BLE device manager."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Set

import websockets
from websockets.server import WebSocketServerProtocol

from yokonex.core.device_manager import DeviceManager
from yokonex.ble.scanner import scan

log = logging.getLogger("yokonex.ws")


class WSServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._manager = DeviceManager()
        self._clients: Set[WebSocketServerProtocol] = set()
        self._manager.add_listener(self._broadcast_event)

    @property
    def manager(self) -> DeviceManager:
        return self._manager

    async def start(self) -> None:
        async with websockets.serve(self._handle_client, self.host, self.port):
            log.info("YokoNex WS server  ws://%s:%d", self.host, self.port)
            await asyncio.Future()

    async def _handle_client(self, ws: WebSocketServerProtocol) -> None:
        self._clients.add(ws)
        log.info("Client connected  total=%d", len(self._clients))
        try:
            async for raw in ws:
                await self._dispatch(ws, raw)
        except websockets.ConnectionClosed:
            pass
        finally:
            self._clients.discard(ws)
            log.info("Client disconnected  total=%d", len(self._clients))

    async def _dispatch(self, ws: WebSocketServerProtocol, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await self._reply(ws, None, {"ok": False, "error": "invalid JSON"})
            return

        req_id = msg.get("id")
        kind   = msg.get("type", "")
        params = msg.get("params", {})

        match kind:
            case "scan":
                duration = float(params.get("duration", 5.0))
                devices = await scan(duration)
                await self._reply(ws, req_id, {"ok": True, "devices": devices})

            case "connect":
                result = await self._manager.connect(
                    address=params["address"],
                    name=params.get("name", ""),
                    device_type=params.get("device_type", "toy"),
                )
                await self._reply(ws, req_id, result)

            case "disconnect":
                result = await self._manager.disconnect(params["address"])
                await self._reply(ws, req_id, result)

            case "command":
                result = await self._manager.command(
                    address=params["address"],
                    action=params["action"],
                    params=params.get("data", {}),
                )
                await self._reply(ws, req_id, result)

            case "list_devices":
                await self._reply(ws, req_id, {
                    "ok": True,
                    "devices": self._manager.list_devices(),
                })

            case _:
                await self._reply(ws, req_id, {"ok": False, "error": f"unknown type: {kind!r}"})

    async def _reply(self, ws: WebSocketServerProtocol, req_id, payload: dict) -> None:
        await ws.send(json.dumps({"id": req_id, **payload}))

    async def _broadcast_event(self, address: str, event: str, data: dict) -> None:
        if not self._clients:
            return
        msg = json.dumps({"type": "event", "address": address, "event": event, "data": data})
        for ws in list(self._clients):
            try:
                await ws.send(msg)
            except Exception:
                pass
