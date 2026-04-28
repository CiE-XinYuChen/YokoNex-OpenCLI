"""Abstract base class for all YokoNex BLE devices.

To add a new device type:
  1. Subclass BaseDevice
  2. Set DEVICE_TYPE, SERVICE_UUID, WRITE_UUID, NOTIFY_UUID
  3. Implement matches(), connect(), disconnect(), handle_command()
  4. Decorate with @register (devices/registry.py)
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ScanResult:
    address: str
    name: str
    device_type: str
    rssi: Optional[int] = None


class BaseDevice(ABC):
    DEVICE_TYPE: str = ""
    SERVICE_UUID: str = ""
    WRITE_UUID: str = ""
    NOTIFY_UUID: str = ""

    # Override in subclass: name prefixes used for name-based BLE discovery.
    # Many devices don't include Service UUID in advertisement packets;
    # name matching is the fallback detection strategy.
    NAME_PREFIXES: List[str] = []

    def __init__(self, address: str, name: str = "") -> None:
        self.address = address
        self.name = name or address
        self._client = None
        self._connected = False
        self._listeners: List[Callable] = []

    # ── Extension points ───────────────────────────────────────────────────

    @classmethod
    @abstractmethod
    def matches(cls, service_uuids: List[str]) -> bool:
        """Return True if BLE advertisement service UUIDs match this device type."""
        ...

    @classmethod
    def matches_name(cls, name: str) -> bool:
        """Return True if the BLE device name matches this device type.

        Default: check NAME_PREFIXES (case-insensitive prefix match).
        Override for custom name-matching logic.
        """
        if not name:
            return False
        name_upper = name.upper()
        return any(name_upper.startswith(p.upper()) for p in cls.NAME_PREFIXES)

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the BLE device. Return True on success."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the BLE device."""
        ...

    @abstractmethod
    async def handle_command(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch a WS API command and return a response dict.

        Every response must contain {"ok": True/False}.
        Unknown actions should return {"ok": False, "error": "unknown action"}.
        """
        ...

    # ── Event system ───────────────────────────────────────────────────────

    def add_listener(self, callback: Callable) -> None:
        """Register async callback(address: str, event: str, data: dict)."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        self._listeners = [c for c in self._listeners if c is not callback]

    async def _emit(self, event: str, data: Dict) -> None:
        for cb in list(self._listeners):
            try:
                await cb(self.address, event, data)
            except Exception:
                pass

    # ── Convenience ────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "name": self.name,
            "type": self.DEVICE_TYPE,
            "connected": self._connected,
        }
