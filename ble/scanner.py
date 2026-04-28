"""BLE scanner — finds YokoNex devices using bleak."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from devices.registry import detect, detect_by_name

log = logging.getLogger("yokonex.ble")


async def scan(duration: float = 5.0) -> List[Dict]:
    """Scan for known YokoNex BLE devices. Returns deduplicated list.

    Detection strategy (in order):
      1. Service UUID match — reliable but many devices omit UUIDs in ad packets.
      2. Device name prefix match — fallback for devices that only advertise by name.
    """
    found: Dict[str, Dict] = {}

    def _callback(device: BLEDevice, ad: AdvertisementData) -> None:
        if device.address in found:
            return

        # Strategy 1: Service UUID
        uuids = [str(u) for u in (ad.service_uuids or [])]
        cls = detect(uuids)

        # Strategy 2: Device name prefix
        if cls is None:
            cls = detect_by_name(device.name or "")

        if cls is None:
            return

        found[device.address] = {
            "address": device.address,
            "name": device.name or "",
            "device_type": cls.DEVICE_TYPE,
            "rssi": ad.rssi,
        }
        log.info(
            "Found %s device: %s (%s)  rssi=%s",
            cls.DEVICE_TYPE, device.name, device.address, ad.rssi,
        )

    async with BleakScanner(detection_callback=_callback):
        await asyncio.sleep(duration)

    return list(found.values())
