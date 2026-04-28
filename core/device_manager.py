"""DeviceManager — lifecycle management for multiple concurrent BLE devices."""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from core.base_device import BaseDevice
from devices.registry import get as get_device_cls

log = logging.getLogger("yokonex.manager")


class DeviceManager:
    """
    Manages connected BLE devices.
    All methods are async and safe to call from the WS server event loop.
    """

    def __init__(self) -> None:
        self._devices: Dict[str, BaseDevice] = {}  # address → device
        self._event_listeners: List[Callable] = []

    # ── Event bus ──────────────────────────────────────────────────────────

    def add_listener(self, callback: Callable) -> None:
        """Register async callback(address, event, data) for ALL devices."""
        self._event_listeners.append(callback)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def connect(self, address: str, name: str, device_type: str) -> Dict:
        if address in self._devices and self._devices[address].is_connected:
            return {"ok": False, "error": "already connected"}

        cls = get_device_cls(device_type)
        if cls is None:
            return {"ok": False, "error": f"unknown device type: {device_type!r}"}

        device = cls(address, name)
        device.add_listener(self._relay_event)

        ok = await device.connect()
        if ok:
            self._devices[address] = device
            log.info("Registered device %s [%s]", address, device_type)
        return {"ok": ok, "address": address, "device_type": device_type}

    async def disconnect(self, address: str) -> Dict:
        device = self._devices.get(address)
        if device is None:
            return {"ok": False, "error": "device not found"}
        await device.disconnect()
        del self._devices[address]
        log.info("Removed device %s", address)
        return {"ok": True, "address": address}

    async def command(self, address: str, action: str, params: Dict) -> Dict:
        device = self._devices.get(address)
        if device is None:
            return {"ok": False, "error": "device not found"}
        return await device.handle_command(action, params)

    def list_devices(self) -> List[Dict]:
        return [d.to_dict() for d in self._devices.values()]

    def get_device(self, address: str) -> Optional[BaseDevice]:
        return self._devices.get(address)

    # ── Internal ───────────────────────────────────────────────────────────

    async def _relay_event(self, address: str, event: str, data: Dict) -> None:
        for cb in list(self._event_listeners):
            try:
                await cb(address, event, data)
            except Exception as exc:
                log.error("Event listener error: %s", exc)
