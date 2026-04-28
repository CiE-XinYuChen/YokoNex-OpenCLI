"""Device type registry — auto-detect device class from BLE advertisement."""
from __future__ import annotations

from typing import Dict, List, Optional, Type

from yokonex.core.base_device import BaseDevice

_registry: Dict[str, Type[BaseDevice]] = {}


def register(cls: Type[BaseDevice]) -> Type[BaseDevice]:
    """Class decorator: register a device implementation."""
    if not cls.DEVICE_TYPE:
        raise ValueError(f"{cls.__name__} must define DEVICE_TYPE")
    _registry[cls.DEVICE_TYPE] = cls
    return cls


def detect(service_uuids: List[str]) -> Optional[Type[BaseDevice]]:
    """Return the first registered device class that matches by Service UUID."""
    for cls in _registry.values():
        if cls.matches(service_uuids):
            return cls
    return None


def detect_by_name(name: str) -> Optional[Type[BaseDevice]]:
    """Return the first registered device class that matches by device name."""
    for cls in _registry.values():
        if cls.matches_name(name):
            return cls
    return None


def get(device_type: str) -> Optional[Type[BaseDevice]]:
    return _registry.get(device_type)


def all_types() -> List[Type[BaseDevice]]:
    return list(_registry.values())
