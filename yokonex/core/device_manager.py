"""DeviceManager — lifecycle management for multiple concurrent BLE devices."""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from yokonex.core.base_device import BaseDevice
from yokonex.devices.registry import get as get_device_cls

log = logging.getLogger("yokonex.manager")


class DeviceManager:
    """
    Manages connected BLE devices.
    All methods are async and safe to call from the WS server event loop.
    """

    def __init__(self) -> None:
        self._devices: Dict[str, BaseDevice] = {}
        self._event_listeners: List[Callable] = []

    def add_listener(self, callback: Callable) -> None:
        """Register async callback(address, event, data) for ALL devices."""
        self._event_listeners.append(callback)

    async def connect(self, address: str, name: str, device_type: str) -> Dict:
        existing = self._devices.get(address)
        if existing is not None:
            if existing.is_connected:
                return {"ok": False, "error": "already connected"}
            # Stale entry from a previous disconnect — clean it up first
            del self._devices[address]

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

    async def _relay_event(self, address: str, event: str, data: Dict) -> None:
        for cb in list(self._event_listeners):
            try:
                await cb(address, event, data)
            except Exception as exc:
                log.error("Event listener error: %s", exc)
