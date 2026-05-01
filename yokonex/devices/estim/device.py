"""EStimDevice — YSKJ_EMS_BLE V1.6（二代电击器）。"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List

from bleak import BleakClient

from yokonex.core.base_device import BaseDevice
from yokonex.devices.registry import register
from . import protocol as proto

log = logging.getLogger("yokonex.estim")

SERVICE_UUID = "0000ff30-0000-1000-8000-00805f9b34fb"
WRITE_UUID   = "0000ff31-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID  = "0000ff32-0000-1000-8000-00805f9b34fb"


@register
class EStimDevice(BaseDevice):
    DEVICE_TYPE  = "estim"
    SERVICE_UUID = SERVICE_UUID
    WRITE_UUID   = WRITE_UUID
    NOTIFY_UUID  = NOTIFY_UUID

    # 扫描时按名称前缀识别（部分设备不广播 Service UUID）
    NAME_PREFIXES = ["YCY-DJQ", "YSKJ-EMS", "YCY-EMS"]

    def __init__(self, address: str, name: str = "") -> None:
        super().__init__(address, name)

        # 通道状态（从设备查询后同步）
        self.channels: Dict[str, Dict] = {
            "A": {"enabled": False, "intensity": 0, "mode": 1, "connection": "disconnected"},
            "B": {"enabled": False, "intensity": 0, "mode": 1, "connection": "disconnected"},
        }
        self.battery: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_resync: float = 0.0  # monotonic time of last _resync_channels call

    # ── BaseDevice interface ───────────────────────────────────────────────

    @classmethod
    def matches(cls, service_uuids: List[str]) -> bool:
        return SERVICE_UUID.lower() in [u.lower() for u in service_uuids]

    async def connect(self) -> bool:
        self._loop = asyncio.get_running_loop()
        self._client = BleakClient(
            self.address,
            disconnected_callback=self._on_ble_disconnect,
        )
        try:
            await self._client.connect()
            await self._client.start_notify(NOTIFY_UUID, self._on_notify)
            self._connected = True
            log.info("Connected to %s (%s)", self.name, self.address)
            # 连接后立即查询双通道状态和电量
            await self._write(proto.build_query(proto.QUERY_CHANNEL_A))
            await asyncio.sleep(0.05)
            await self._write(proto.build_query(proto.QUERY_CHANNEL_B))
            await asyncio.sleep(0.05)
            await self._write(proto.build_query(proto.QUERY_BATTERY))
            await self._emit("connected", self.to_dict())
            return True
        except Exception as exc:
            self._connected = False
            log.error("Connect failed %s: %s", self.address, exc)
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
            await self._emit("error", {"message": str(exc)})
            return False

    async def disconnect(self) -> None:
        if self._client and self._connected:
            # 断开前关闭所有通道
            try:
                await self._write(proto.build_stop())
            except Exception:
                pass
            await self._client.disconnect()
        self._connected = False

    async def handle_command(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._connected:
            return {"ok": False, "error": "not connected"}

        match action:

            case "set_channel":
                # params: channel "A"|"B"|"AB", enabled bool,
                #         intensity 1-276, mode 1-17,
                #         freq 0-100 (custom mode only),
                #         pulse_us 0-100 (custom mode only)
                ch        = str(params.get("channel", "A")).upper()
                enabled   = bool(params.get("enabled", True))
                intensity = int(params.get("intensity", 1))
                mode      = int(params.get("mode", 1))
                freq      = int(params.get("freq", 0))
                pulse_us  = int(params.get("pulse_us", 0))
                await self._write(proto.build_channel(ch, enabled, intensity, mode, freq, pulse_us))
                # 更新本地状态（AB 同时更新）
                targets = list(self.channels) if ch == "AB" else [ch] if ch in self.channels else []
                for t in targets:
                    self.channels[t]["enabled"]   = enabled
                    self.channels[t]["intensity"]  = intensity if enabled else 0
                    self.channels[t]["mode"]       = mode
                return {"ok": True}

            case "stop":
                if any(c.get("enabled") for c in self.channels.values()):
                    await self._write(proto.build_stop())
                for ch in self.channels.values():
                    ch["enabled"]   = False
                    ch["intensity"] = 0
                return {"ok": True}

            case "set_motor":
                # state: 0=off, 1=on, 0x11/0x12/0x13=preset1/2/3
                state = int(params.get("state", 0))
                await self._write(proto.build_motor(state))
                return {"ok": True}

            case "set_step":
                # state: "start"|"stop"|"reset"|"pause"|"resume"
                _step_map = {
                    "start":  proto.STEP_START,
                    "stop":   proto.STEP_STOP,
                    "reset":  proto.STEP_RESET,
                    "pause":  proto.STEP_PAUSE,
                    "resume": proto.STEP_RESUME,
                }
                state_str = str(params.get("state", "stop")).lower()
                state_val = _step_map.get(state_str, proto.STEP_STOP)
                await self._write(proto.build_step(state_val))
                return {"ok": True}

            case "set_angle":
                enabled = bool(params.get("enabled", False))
                await self._write(proto.build_angle(enabled))
                return {"ok": True}

            case "get_channel":
                ch = str(params.get("channel", "A")).upper()
                qtype = proto.QUERY_CHANNEL_A if ch == "A" else proto.QUERY_CHANNEL_B
                await self._write(proto.build_query(qtype))
                return {"ok": True, "channel": ch, **self.channels.get(ch, {})}

            case "get_battery":
                await self._write(proto.build_query(proto.QUERY_BATTERY))
                return {"ok": True, "battery": self.battery}

            case "get_step":
                await self._write(proto.build_query(proto.QUERY_STEP))
                return {"ok": True}

            case "get_angle":
                await self._write(proto.build_query(proto.QUERY_ANGLE))
                return {"ok": True}

            case "get_info":
                return {
                    "ok":       True,
                    "channels": self.channels,
                    "battery":  self.battery,
                    **self.to_dict(),
                }

        return {"ok": False, "error": f"unknown action: {action!r}"}

    # ── Internal ───────────────────────────────────────────────────────────

    async def _resync_channels(self) -> None:
        now = time.monotonic()
        if now - self._last_resync < 2.0:
            return  # cooldown: don't resync more than once every 2 s
        self._last_resync = now
        try:
            await self._write(proto.build_query(proto.QUERY_CHANNEL_A))
            await asyncio.sleep(0.05)
            await self._write(proto.build_query(proto.QUERY_CHANNEL_B))
        except Exception as exc:
            log.error("Resync failed: %s", exc)

    async def _write(self, data: bytes) -> None:
        log.debug("→ tx  %s", data.hex())
        await self._client.write_gatt_char(WRITE_UUID, data, response=False)

    def _on_ble_disconnect(self, _client: BleakClient) -> None:
        self._connected = False
        log.warning("Disconnected: %s", self.address)
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._emit("disconnected", {"address": self.address}),
                self._loop,
            )

    def _on_notify(self, _handle: int, data: bytearray) -> None:
        log.debug("← rx  %s", data.hex())
        parsed = proto.parse_notify(bytes(data))
        if not parsed or parsed["type"] == "raw":
            if parsed:
                log.debug("unhandled notify: %s", parsed["hex"])
            return
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._apply_notify(parsed), self._loop
            )

    async def _apply_notify(self, parsed: dict) -> None:
        """Process a parsed notify packet in the asyncio loop thread."""
        emit = True
        match parsed["type"]:
            case "channel_status":
                ch = parsed.get("channel")
                if ch in self.channels:
                    new = {
                        "enabled":    parsed["enabled"],
                        "intensity":  parsed["intensity"],
                        "mode":       parsed["mode"],
                        "connection": parsed["connection"],
                    }
                    # suppress event if nothing changed (device sends this repeatedly)
                    if all(self.channels[ch].get(k) == v for k, v in new.items()):
                        emit = False
                    else:
                        self.channels[ch].update(new)
            case "battery":
                emit = self.battery != parsed["level"]
                self.battery = parsed["level"]
            case "device_error":
                log.warning("Device error %s: %s", self.address, parsed["code"])
                await self._resync_channels()
                emit = False

        if emit:
            await self._emit(parsed["type"], parsed)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["channels"] = self.channels
        d["battery"]  = self.battery
        return d
