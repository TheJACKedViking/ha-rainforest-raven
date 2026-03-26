"""Tests for RAVEnDataCoordinator connection handling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rainforest_raven.const import (
    POLLING_INTERVAL_SECONDS,
    TIMEOUT_DEVICE_CLEANUP,
    TIMEOUT_DEVICE_CONNECT,
    TIMEOUT_DEVICE_DATA,
)
from rainforest_raven.coordinator import RAVEnDataCoordinator
import rainforest_raven.coordinator as _coord_mod
from tests.conftest import MockRAVEnDeviceInfo, MOCK_METER_MAC

# IMPORTANT: Import exception classes from the coordinator module, not tests.conftest.
# Pytest loads conftest.py twice (as 'conftest' and 'tests.conftest'), creating two
# distinct exception classes. The coordinator's except clauses use the 'conftest' copy,
# so tests must raise that same copy for except matching to work.
RAVEnConnectionError = _coord_mod.RAVEnConnectionError
UpdateFailed = _coord_mod.UpdateFailed


def _make_coordinator(device=None, config_entry=None):
    """Create a coordinator without calling __init__."""
    coord = RAVEnDataCoordinator.__new__(RAVEnDataCoordinator)
    coord._raven_device = device
    coord._device_info = MockRAVEnDeviceInfo() if device else None
    coord.config_entry = config_entry or MagicMock(
        data={"device": "/dev/ttyUSB0", "mac": [MOCK_METER_MAC]}
    )
    return coord


# ── _cleanup_device tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_cleanup_device_timeout_does_not_hang():
    """_cleanup_device must not hang when close() blocks forever."""
    device = AsyncMock()

    async def blocking_close():
        await asyncio.sleep(999)

    device.close = AsyncMock(side_effect=blocking_close)
    device.abort = AsyncMock()

    coord = _make_coordinator(device=device)

    # Use a short timeout to keep the test fast
    with patch("rainforest_raven.coordinator.TIMEOUT_DEVICE_CLEANUP", 0.01):
        # Should complete quickly, not hang
        try:
            async with asyncio.timeout(2):
                await coord._cleanup_device()
        except TimeoutError:
            pytest.fail("_cleanup_device hung beyond the expected timeout")

    # Device reference should be cleared
    assert coord._raven_device is None


@pytest.mark.asyncio
async def test_cleanup_device_calls_abort_on_close_timeout():
    """When close() times out, abort() should be called as fallback."""
    device = AsyncMock()

    async def blocking_close():
        await asyncio.sleep(999)

    device.close = AsyncMock(side_effect=blocking_close)
    device.abort = AsyncMock()

    coord = _make_coordinator(device=device)

    with patch("rainforest_raven.coordinator.TIMEOUT_DEVICE_CLEANUP", 0.01):
        await coord._cleanup_device()

    device.abort.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_device_close_exception_triggers_abort():
    """When close() raises, abort() should be called."""
    device = AsyncMock()
    device.close = AsyncMock(side_effect=OSError("device gone"))
    device.abort = AsyncMock()

    coord = _make_coordinator(device=device)
    await coord._cleanup_device()

    device.abort.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_device_abort_failure_does_not_raise():
    """If both close() and abort() fail, _cleanup_device must not raise."""
    device = AsyncMock()
    device.close = AsyncMock(side_effect=OSError("close failed"))
    device.abort = AsyncMock(side_effect=OSError("abort failed"))

    coord = _make_coordinator(device=device)

    # Must not raise
    await coord._cleanup_device()

    assert coord._raven_device is None


@pytest.mark.asyncio
async def test_cleanup_device_noop_when_no_device():
    """_cleanup_device is a no-op when no device is set."""
    coord = _make_coordinator(device=None)
    await coord._cleanup_device()
    assert coord._raven_device is None


@pytest.mark.asyncio
async def test_cleanup_device_happy_path():
    """Normal close should work without calling abort."""
    device = AsyncMock()
    device.close = AsyncMock()
    device.abort = AsyncMock()

    coord = _make_coordinator(device=device)
    await coord._cleanup_device()

    device.close.assert_awaited_once()
    device.abort.assert_not_awaited()
    assert coord._raven_device is None


# ── _get_device tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_device_returns_existing():
    """If a device is already cached, return it directly."""
    device = AsyncMock()
    coord = _make_coordinator(device=device)
    result = await coord._get_device()
    assert result is device


@pytest.mark.asyncio
async def test_get_device_connection_error_reraises():
    """_get_device re-raises the original error after calling abort."""
    mock_device = AsyncMock()
    mock_device.open = AsyncMock(side_effect=RAVEnConnectionError("no device"))
    mock_device.abort = AsyncMock()

    coord = _make_coordinator(device=None)

    with patch("rainforest_raven.coordinator.RAVEnSerialDevice", return_value=mock_device):
        with pytest.raises(RAVEnConnectionError, match="no device"):
            await coord._get_device()

    mock_device.abort.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_device_abort_failure_does_not_mask_original():
    """If abort() fails during error recovery, the original error is still raised."""
    mock_device = AsyncMock()
    mock_device.open = AsyncMock(side_effect=RAVEnConnectionError("original error"))
    mock_device.abort = AsyncMock(side_effect=OSError("abort failed"))

    coord = _make_coordinator(device=None)

    with patch("rainforest_raven.coordinator.RAVEnSerialDevice", return_value=mock_device):
        with pytest.raises(RAVEnConnectionError, match="original error"):
            await coord._get_device()

    mock_device.abort.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_device_timeout_calls_abort():
    """If connection times out, abort() is called and TimeoutError raised."""
    mock_device = AsyncMock()

    async def blocking_open():
        await asyncio.sleep(999)

    mock_device.open = AsyncMock(side_effect=blocking_open)
    mock_device.abort = AsyncMock()

    coord = _make_coordinator(device=None)

    with patch("rainforest_raven.coordinator.RAVEnSerialDevice", return_value=mock_device):
        with patch("rainforest_raven.coordinator.TIMEOUT_DEVICE_CONNECT", 0.01):
            with pytest.raises(TimeoutError):
                await coord._get_device()

    mock_device.abort.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_device_successful_connection():
    """Successful connection stores device and device_info."""
    mock_device = AsyncMock()
    mock_device.open = AsyncMock()
    mock_device.synchronize = AsyncMock()
    mock_device.get_device_info = AsyncMock(return_value=MockRAVEnDeviceInfo())

    coord = _make_coordinator(device=None)

    with patch("rainforest_raven.coordinator.RAVEnSerialDevice", return_value=mock_device):
        result = await coord._get_device()

    assert result is mock_device
    assert coord._raven_device is mock_device
    assert coord._device_info is not None


# ── Constants sanity checks ────────────────────────────────────


def test_timeout_constants_are_positive():
    """All timeout constants must be positive numbers."""
    assert TIMEOUT_DEVICE_CONNECT > 0
    assert TIMEOUT_DEVICE_CLEANUP > 0
    assert TIMEOUT_DEVICE_DATA > 0


def test_polling_interval_is_sensible():
    """Polling interval should be between 10s and 300s."""
    assert 10 <= POLLING_INTERVAL_SECONDS <= 300


def test_cleanup_timeout_less_than_connect():
    """Cleanup timeout should be shorter than connection timeout."""
    assert TIMEOUT_DEVICE_CLEANUP <= TIMEOUT_DEVICE_CONNECT


# ── _async_update_data retry tests ─────────────────────────────


@pytest.mark.asyncio
async def test_update_data_retries_once_on_timeout():
    """First call times out, synchronize called, second call succeeds.

    Connection should NOT be torn down (no cleanup).
    """
    mock_device = AsyncMock()
    mock_device.synchronize = AsyncMock()
    mock_device.close = AsyncMock()
    mock_device.abort = AsyncMock()

    call_count = 0

    async def fake_get_all_data(device, meter_macs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError("first attempt timeout")
        return {"Meters": {}}

    coord = _make_coordinator(device=mock_device)

    with patch("rainforest_raven.coordinator._get_all_data", side_effect=fake_get_all_data):
        result = await coord._async_update_data()

    assert result == {"Meters": {}}
    assert call_count == 2
    mock_device.synchronize.assert_awaited_once()
    # Connection should NOT have been torn down
    assert coord._raven_device is mock_device


@pytest.mark.asyncio
async def test_update_data_retries_once_on_connection_error():
    """First call raises RAVEnConnectionError, connection torn down, second succeeds."""
    mock_device = AsyncMock()
    mock_device.close = AsyncMock()
    mock_device.abort = AsyncMock()
    mock_device.open = AsyncMock()
    mock_device.synchronize = AsyncMock()
    mock_device.get_device_info = AsyncMock(return_value=MockRAVEnDeviceInfo())

    call_count = 0

    async def fake_get_all_data(device, meter_macs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RAVEnConnectionError("first attempt connection error")
        return {"Meters": {}}

    coord = _make_coordinator(device=mock_device)

    with patch("rainforest_raven.coordinator._get_all_data", side_effect=fake_get_all_data), \
         patch("rainforest_raven.coordinator.RAVEnSerialDevice", return_value=mock_device):
        result = await coord._async_update_data()

    assert result == {"Meters": {}}
    assert call_count == 2
    # close should have been called during cleanup
    mock_device.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_data_raises_after_two_consecutive_timeouts():
    """Both attempts timeout. Raises UpdateFailed with 'timed out' message."""
    mock_device = AsyncMock()
    mock_device.synchronize = AsyncMock()
    mock_device.close = AsyncMock()
    mock_device.abort = AsyncMock()

    async def fake_get_all_data(device, meter_macs):
        raise TimeoutError("timeout")

    coord = _make_coordinator(device=mock_device)

    with patch("rainforest_raven.coordinator._get_all_data", side_effect=fake_get_all_data):
        with pytest.raises(UpdateFailed, match="timed out"):
            await coord._async_update_data()

    # Connection should be cleaned up after second failure
    assert coord._raven_device is None


@pytest.mark.asyncio
async def test_update_data_raises_after_two_consecutive_connection_errors():
    """Both attempts raise RAVEnConnectionError. Raises UpdateFailed."""
    mock_device = AsyncMock()
    mock_device.close = AsyncMock()
    mock_device.abort = AsyncMock()
    mock_device.open = AsyncMock()
    mock_device.synchronize = AsyncMock()
    mock_device.get_device_info = AsyncMock(return_value=MockRAVEnDeviceInfo())

    async def fake_get_all_data(device, meter_macs):
        raise RAVEnConnectionError("connection error")

    coord = _make_coordinator(device=mock_device)

    with patch("rainforest_raven.coordinator._get_all_data", side_effect=fake_get_all_data), \
         patch("rainforest_raven.coordinator.RAVEnSerialDevice", return_value=mock_device):
        with pytest.raises(UpdateFailed, match="RAVEnConnectionError"):
            await coord._async_update_data()

    # Connection should be cleaned up
    assert coord._raven_device is None


@pytest.mark.asyncio
async def test_update_data_resync_failure_raises_update_failed():
    """First call times out, synchronize also fails. Raises UpdateFailed with 'resynchronize'."""
    mock_device = AsyncMock()
    mock_device.synchronize = AsyncMock(side_effect=OSError("sync failed"))
    mock_device.close = AsyncMock()
    mock_device.abort = AsyncMock()

    async def fake_get_all_data(device, meter_macs):
        raise TimeoutError("timeout")

    coord = _make_coordinator(device=mock_device)

    with patch("rainforest_raven.coordinator._get_all_data", side_effect=fake_get_all_data):
        with pytest.raises(UpdateFailed, match="resynchronize"):
            await coord._async_update_data()

    # Connection should be cleaned up after resync failure
    assert coord._raven_device is None
