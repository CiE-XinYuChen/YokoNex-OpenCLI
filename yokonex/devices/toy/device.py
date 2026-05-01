"""ToyDevice — YSKJ_TOY_BLE V1.1 (飞机杯 / 跳蛋 / 多马达玩具)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from bleak import BleakClient

from yokonex.core.base_device import BaseDevice
from yokonex.devices.registry import register
from . import protocol as proto

log = logging.getLogger("yokonex.toy")

SERVICE_UUID = "0000ff40-0000-1000-8000-00805f9b34fb"
WRITE_UUID   = "0000ff41-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID  = "0000ff42-0000-1000-8000-00805f9b34fb"


@register
class ToyDevice(BaseDevice):
    DEVICE_TYPE = "toy"
    SERVICE_UUID = SERVICE_UUID
    WRITE_UUID   = WRITE_UUID
    NOTIFY_UUID  = NOTIFY_UUID

    # Devices in this family advertise by name rather than Service UUID.
    # Known prefixes: YCY-FJB (飞机杯), YCY-TDD (跳蛋)
    NAME_PREFIXES = ["YCY-FJB", "YCY-TDD"]

    def __init__(self, address: str, name: str = "") -> None:
        super().__init__(address, name)
        self.motor_a_modes = 0
        self.motor_b_modes = 0
        self.motor_c_modes = 0
        self.battery: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

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
            await self._write(proto.build_device_info_query())
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
            await self._client.disconnect()
        self._connected = False

    async def handle_command(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._connected:
            return {"ok": False, "error": "not connected"}

        match action:
            case "set_mode":
                motors = _parse_motors(params.get("motors", "A"))
                mode   = int(params.get("mode", 1))
                await self._write(proto.build_fixed_mode(motors, mode))
                return {"ok": True}

            case "set_speed":
                await self._write(proto.build_speed(
                    motor_a=int(params.get("motor_a", 0)),
                    motor_b=int(params.get("motor_b", 0)),
                    motor_c=int(params.get("motor_c", 0)),
                ))
                return {"ok": True}

            case "stop":
                await self._write(proto.build_fixed_mode(proto.MOTOR_ALL, 0))
                return {"ok": True}

            case "get_info":
                return {
                    "ok": True,
                    "motor_a_modes": self.motor_a_modes,
                    "motor_b_modes": self.motor_b_modes,
                    "motor_c_modes": self.motor_c_modes,
                    "battery": self.battery,
                    **self.to_dict(),
                }

        return {"ok": False, "error": f"unknown action: {action}"}

    # ── Internal ───────────────────────────────────────────────────────────

    async def _write(self, data: bytes) -> None:
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
        parsed = proto.parse_notify(bytes(data))
        if not parsed:
            return

        match parsed["type"]:
            case "heartbeat":
                return
            case "raw":
                log.debug("unhandled notify: %s", parsed["hex"])
                return
            case "device_info":
                self.motor_a_modes = parsed["motor_a_modes"]
                self.motor_b_modes = parsed["motor_b_modes"]
                self.motor_c_modes = parsed["motor_c_modes"]
            case "battery":
                self.battery = parsed["level"]

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._emit(parsed["type"], parsed),
                self._loop,
            )


def _parse_motors(value) -> int:
    """Accept int bitmask or string like 'A', 'AB', 'ABC'."""
    if isinstance(value, int):
        return value & 0x07
    m = 0
    s = str(value).upper()
    if "A" in s:
        m |= proto.MOTOR_A
    if "B" in s:
        m |= proto.MOTOR_B
    if "C" in s:
        m |= proto.MOTOR_C
    return m or proto.MOTOR_A
