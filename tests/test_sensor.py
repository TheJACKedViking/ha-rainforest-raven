"""Tests for RAVEn sensor entities."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.conftest import MOCK_METER_MAC


def _make_coordinator(data: dict) -> MagicMock:
    """Create a mock coordinator with given data."""
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.device_mac_address = "001122334455aabb"
    coordinator.device_info = MagicMock()
    return coordinator


def test_native_value_returns_none_when_data_missing():
    """Test that missing data returns None, not the string 'None'."""
    from rainforest_raven.sensor import RAVEnSensor, DIAGNOSTICS

    coordinator = _make_coordinator({})
    sensor = RAVEnSensor.__new__(RAVEnSensor)
    sensor.coordinator = coordinator
    sensor.entity_description = DIAGNOSTICS[0]

    value = sensor.native_value
    assert value is None, f"Expected None, got {value!r}"


def test_native_value_returns_actual_value_when_present():
    """Test that valid data is returned correctly."""
    from rainforest_raven.sensor import RAVEnSensor, DIAGNOSTICS

    coordinator = _make_coordinator({"NetworkInfo": {"link_strength": 85, "channel": 15}})
    sensor = RAVEnSensor.__new__(RAVEnSensor)
    sensor.coordinator = coordinator
    sensor.entity_description = DIAGNOSTICS[0]

    assert sensor.native_value == 85


def test_meter_sensor_native_value_returns_none_when_meter_data_missing():
    """Test meter sensor returns None when meter data is absent."""
    from rainforest_raven.sensor import RAVEnMeterSensor, SENSORS

    coordinator = _make_coordinator({"Meters": {}})
    sensor = RAVEnMeterSensor.__new__(RAVEnMeterSensor)
    sensor.coordinator = coordinator
    sensor.entity_description = SENSORS[0]
    sensor._meter_mac_addr = MOCK_METER_MAC

    assert sensor.native_value is None


@pytest.mark.asyncio
async def test_price_sensor_created_even_without_initial_price_data():
    """Test that price sensor is always created for each meter."""
    from rainforest_raven.sensor import async_setup_entry

    coordinator = _make_coordinator({"Meters": {MOCK_METER_MAC: {}}})

    entry = MagicMock()
    entry.data = {"mac": [MOCK_METER_MAC]}
    entry.runtime_data = coordinator

    added_entities = []
    await async_setup_entry(MagicMock(), entry, lambda entities: added_entities.extend(entities))

    entity_keys = [e.entity_description.key for e in added_entities]
    assert "price" in entity_keys, f"Price sensor should always be created. Got: {entity_keys}"


def test_price_sensor_unit_is_none_when_currency_unavailable():
    """Test that price sensor unit is None when no currency data exists."""
    from rainforest_raven.sensor import RAVEnPriceSensor, PRICE_SENSOR

    coordinator = _make_coordinator({"Meters": {MOCK_METER_MAC: {"PriceCluster": {}}}})
    sensor = RAVEnPriceSensor.__new__(RAVEnPriceSensor)
    sensor.coordinator = coordinator
    sensor.entity_description = PRICE_SENSOR
    sensor._meter_mac_addr = MOCK_METER_MAC
    sensor._cached_unit = None

    assert sensor.native_unit_of_measurement is None


def test_price_sensor_unit_cached_once_discovered():
    """Test that price sensor caches unit after first discovery."""
    from rainforest_raven.sensor import RAVEnPriceSensor, PRICE_SENSOR

    coordinator = _make_coordinator({
        "Meters": {
            MOCK_METER_MAC: {
                "PriceCluster": {"currency": MagicMock(value="USD"), "price": 0.12}
            }
        }
    })
    sensor = RAVEnPriceSensor.__new__(RAVEnPriceSensor)
    sensor.coordinator = coordinator
    sensor.entity_description = PRICE_SENSOR
    sensor._meter_mac_addr = MOCK_METER_MAC
    sensor._cached_unit = None

    unit = sensor.native_unit_of_measurement
    assert "USD" in unit
    assert "kWh" in unit

    # Now: currency disappears (transient data gap)
    coordinator.data = {"Meters": {MOCK_METER_MAC: {"PriceCluster": {}}}}
    unit_after_gap = sensor.native_unit_of_measurement
    assert unit_after_gap == unit, "Unit should remain cached after data gap"
