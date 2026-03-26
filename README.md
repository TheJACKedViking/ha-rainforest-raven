# Rainforest RAVEn for Home Assistant

A custom Home Assistant integration for **Rainforest RAVEn** and **EMU-2** USB energy monitoring devices. This is a fork of the [built-in HA integration](https://www.home-assistant.io/integrations/rainforest_raven) with significant reliability and usability improvements.

## What's Improved

### USB Connection Reliability
- **Timeout on device close** -- prevents the event loop from hanging when the USB device is stuck
- **Retry before teardown** -- transient errors trigger a resync and retry instead of immediately tearing down the serial connection
- **Safer exception handling** -- replaced bare `except:` with proper error handling that doesn't mask real failures
- **Increased timeouts** -- connect (10s), data fetch (15s), and polling (60s) are tuned for real-world USB serial behavior

### Bug Fixes
- **Sensor values no longer show "None"** -- missing data returns actual `None` (unavailable) instead of the string `"None"`
- **Price sensor always created** -- no longer requires a reload if price data arrives after initial setup; unit of measurement is cached to prevent HA statistics resets
- **Config flow: empty meter discovery** -- aborts gracefully with a clear message instead of showing an empty dropdown
- **Config flow: empty meter selection** -- shows an error when submitting without selecting a meter
- **Config flow: device disconnect** -- handles the device disappearing between form display and submission

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots in the top right and select **Custom repositories**
3. Add `https://github.com/TheJACKedViking/ha-rainforest-raven` with category **Integration**
4. Search for "Rainforest RAVEn" and install it
5. Restart Home Assistant

### Manual

1. Download the latest release
2. Copy the `custom_components/rainforest_raven` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

After installation, go to **Settings > Devices & Services > Add Integration** and search for "Rainforest RAVEn". Plug in your RAVEn or EMU-2 device and follow the setup wizard.

## Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| Total energy delivered | Cumulative energy consumed | kWh |
| Total energy received | Cumulative energy fed back (solar) | kWh |
| Power demand | Instantaneous power draw | kW |
| Energy price | Current electricity rate | currency/kWh |
| Signal strength | Zigbee link quality | % |

## Supported Devices

- Rainforest RAVEn (USB VID: 0403, PID: 8A28)
- Rainforest EMU-2 (USB VID: 04B4, PID: 0003)

## License

MIT
