"""Tests for RAVEn config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_meters_step_aborts_when_no_meters_found():
    """Test that config flow aborts if no electric meters were discovered."""
    from rainforest_raven.config_flow import RainforestRavenConfigFlow

    flow = RainforestRavenConfigFlow()
    flow._meter_macs = set()
    flow._dev_path = "/dev/ttyUSB0"
    flow.async_abort = MagicMock(return_value={"type": "abort", "reason": "no_meters_found"})

    result = await flow.async_step_meters()

    flow.async_abort.assert_called_once_with(reason="no_meters_found")
    assert result["type"] == "abort"


@pytest.mark.asyncio
async def test_meters_step_shows_form_when_meters_exist():
    """Test that meters form is shown when meters are available."""
    from rainforest_raven.config_flow import RainforestRavenConfigFlow

    flow = RainforestRavenConfigFlow()
    flow._meter_macs = {"aabbccdd11223344"}
    flow._dev_path = "/dev/ttyUSB0"
    flow.async_show_form = MagicMock(return_value={"type": "form"})

    result = await flow.async_step_meters()

    flow.async_show_form.assert_called_once()


@pytest.mark.asyncio
async def test_meters_step_shows_error_when_no_meters_selected():
    """Test that submitting meters form without selection shows an error."""
    from rainforest_raven.config_flow import RainforestRavenConfigFlow

    flow = RainforestRavenConfigFlow()
    flow._meter_macs = {"aabbccdd11223344"}
    flow._dev_path = "/dev/ttyUSB0"
    flow.async_show_form = MagicMock(return_value={"type": "form", "errors": {"mac": "no_meters_selected"}})

    result = await flow.async_step_meters(user_input={"mac": []})

    call_kwargs = flow.async_show_form.call_args
    errors = call_kwargs.kwargs.get("errors", {}) if call_kwargs.kwargs else call_kwargs[1].get("errors", {})
    assert "mac" in errors


@pytest.mark.asyncio
async def test_user_step_handles_device_disconnected():
    """Test graceful handling when selected device disappears."""
    from rainforest_raven.config_flow import RainforestRavenConfigFlow

    flow = RainforestRavenConfigFlow()
    flow.hass = MagicMock()
    flow._async_in_progress = MagicMock(return_value=False)
    flow._async_current_entries = MagicMock(return_value=[])
    flow.async_abort = MagicMock(return_value={"type": "abort", "reason": "no_devices_found"})

    # comports returns empty list - device is gone
    flow.hass.async_add_executor_job = AsyncMock(return_value=[])

    result = await flow.async_step_user(
        user_input={"device": "Some Device That No Longer Exists"}
    )

    # Should abort, not crash with ValueError
    assert result["type"] in ("form", "abort")
