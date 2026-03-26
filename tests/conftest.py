"""Shared test fixtures for Rainforest RAVEn tests.

sys.modules mocking happens at the top of this file, before any
integration code is imported.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ============================================================
# Real exception classes (tests must be able to catch these)
# ============================================================

class UpdateFailed(Exception):
    """Mock HA UpdateFailed."""


class RAVEnConnectionError(Exception):
    """Mock aioraven connection error."""


# ============================================================
# Real DataUpdateCoordinator base class
# ============================================================

class _MockDataUpdateCoordinator:
    """Minimal DataUpdateCoordinator mock for testing."""

    def __init__(self, hass=None, logger=None, *, config_entry=None, name=None, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.config_entry = config_entry
        self.name = name
        self.update_interval = update_interval
        self.data = {}

    async def async_config_entry_first_refresh(self):
        pass

    async def async_shutdown(self):
        pass


class _MockCoordinatorEntity:
    """Mock CoordinatorEntity that supports generic subscripting."""

    def __init__(self, coordinator=None):
        self.coordinator = coordinator

    def __class_getitem__(cls, item):
        return cls


@dataclass(frozen=True)
class _MockSensorEntityDescription:
    """Mock SensorEntityDescription for subclass compatibility."""

    key: str = ""
    translation_key: str | None = None
    native_unit_of_measurement: str | None = None
    device_class: Any = None
    state_class: Any = None
    entity_category: Any = None

    def __init_subclass__(cls, **kw: Any) -> None:
        pass


# ============================================================
# Construct and install mock modules into sys.modules
# ============================================================

_ha_const = MagicMock()
_ha_const.CONF_DEVICE = "device"
_ha_const.CONF_MAC = "mac"
_ha_const.CONF_NAME = "name"
_ha_const.Platform = MagicMock(SENSOR="sensor")
_ha_const.PERCENTAGE = "%"
_ha_const.EntityCategory = MagicMock(DIAGNOSTIC="diagnostic")
_ha_const.UnitOfEnergy = MagicMock(KILO_WATT_HOUR="kWh")
_ha_const.UnitOfPower = MagicMock(KILO_WATT="kW")

_update_coordinator_mod = MagicMock()
_update_coordinator_mod.DataUpdateCoordinator = _MockDataUpdateCoordinator
_update_coordinator_mod.UpdateFailed = UpdateFailed
_update_coordinator_mod.CoordinatorEntity = _MockCoordinatorEntity

_aioraven_device_mod = MagicMock()
_aioraven_device_mod.RAVEnConnectionError = RAVEnConnectionError

_sensor_mod = MagicMock()
_sensor_mod.SensorDeviceClass = MagicMock(ENERGY="energy", POWER="power")
_sensor_mod.SensorEntity = type("SensorEntity", (), {"_attr_has_entity_name": False})
_sensor_mod.SensorEntityDescription = _MockSensorEntityDescription
_sensor_mod.SensorStateClass = MagicMock(
    TOTAL_INCREASING="total_increasing", MEASUREMENT="measurement"
)

_config_entries_mod = MagicMock()
_config_entries_mod.ConfigEntry = type("ConfigEntry", (), {})
_config_entries_mod.ConfigFlow = type(
    "ConfigFlow",
    (),
    {"__init_subclass__": classmethod(lambda cls, **kw: None)},
)
_config_entries_mod.ConfigFlowResult = dict

_mocks = {
    "homeassistant": MagicMock(),
    "homeassistant.const": _ha_const,
    "homeassistant.core": MagicMock(),
    "homeassistant.config_entries": _config_entries_mod,
    "homeassistant.components": MagicMock(),
    "homeassistant.components.usb": MagicMock(),
    "homeassistant.components.sensor": _sensor_mod,
    "homeassistant.components.diagnostics": MagicMock(),
    "homeassistant.helpers": MagicMock(),
    "homeassistant.helpers.device_registry": MagicMock(),
    "homeassistant.helpers.update_coordinator": _update_coordinator_mod,
    "homeassistant.helpers.entity_platform": MagicMock(),
    "homeassistant.helpers.typing": MagicMock(),
    "homeassistant.helpers.selector": MagicMock(),
    "homeassistant.helpers.service_info": MagicMock(),
    "homeassistant.helpers.service_info.usb": MagicMock(),
    "aioraven": MagicMock(),
    "aioraven.data": MagicMock(),
    "aioraven.device": _aioraven_device_mod,
    "aioraven.serial": MagicMock(),
    "serial": MagicMock(),
    "serial.tools": MagicMock(),
    "serial.tools.list_ports": MagicMock(),
    "serial.tools.list_ports_common": MagicMock(),
    "voluptuous": MagicMock(),
}

for mod_name, mock_obj in _mocks.items():
    sys.modules[mod_name] = mock_obj


# ============================================================
# Mock data classes
# ============================================================

@dataclass
class MockRAVEnDeviceInfo:
    """Mock RAVEn device info."""

    manufacturer: str = "Rainforest"
    model_id: str = "RAVEn"
    fw_version: str = "2.0.0"
    hw_version: str = "7.2"
    device_mac_id: bytes = b"\x00\x11\x22\x33\x44\x55\xaa\xbb"


@dataclass
class MockSummationInfo:
    """Mock summation data."""

    meter_mac_id: bytes = b"\xaa\xbb\xcc\xdd\x11\x22\x33\x44"
    summation_delivered: float = 12345.678
    summation_received: float = 0.0


@dataclass
class MockDemandInfo:
    """Mock demand data."""

    meter_mac_id: bytes = b"\xaa\xbb\xcc\xdd\x11\x22\x33\x44"
    demand: float = 1.234


@dataclass
class MockPriceInfo:
    """Mock price data."""

    meter_mac_id: bytes = b"\xaa\xbb\xcc\xdd\x11\x22\x33\x44"
    price: float = 0.12
    currency: None = None
    tier: int = 1
    rate_label: str = "default"


@dataclass
class MockNetworkInfo:
    """Mock network info."""

    link_strength: int = 85
    channel: int = 15


@dataclass
class MockMeterList:
    """Mock meter list."""

    meter_mac_ids: list[bytes] | None = None

    def __post_init__(self):
        if self.meter_mac_ids is None:
            self.meter_mac_ids = [b"\xaa\xbb\xcc\xdd\x11\x22\x33\x44"]


MOCK_METER_MAC = "aabbccdd11223344"
MOCK_METER_MAC_BYTES = bytes.fromhex(MOCK_METER_MAC)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def mock_raven_device():
    """Create a mock RAVEn serial device."""
    device = AsyncMock()
    device.open = AsyncMock()
    device.close = AsyncMock()
    device.abort = AsyncMock()
    device.synchronize = AsyncMock()
    device.get_device_info = AsyncMock(return_value=MockRAVEnDeviceInfo())
    device.get_meter_list = AsyncMock(return_value=MockMeterList())
    device.get_meter_info = AsyncMock()
    device.get_current_summation_delivered = AsyncMock(return_value=MockSummationInfo())
    device.get_instantaneous_demand = AsyncMock(return_value=MockDemandInfo())
    device.get_current_price = AsyncMock(return_value=MockPriceInfo())
    device.get_network_info = AsyncMock(return_value=MockNetworkInfo())
    return device


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {
        "device": "/dev/ttyUSB0",
        "mac": [MOCK_METER_MAC],
    }
    entry.entry_id = "test_entry_id"
    return entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass
