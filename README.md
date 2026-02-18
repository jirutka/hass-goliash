# Goliash Integration

[![GitHub Release][releases-shield]][releases]

Home Assistant integration for [Goliash](https://app.goliash.cz) API.


## Installation

### Using Home Assistant Community Store (HACS)

1. Ensure that [HACS] is installed.
1. Go to **HACS > Integrations**.
1. Click on the hamburger menu in the top right corner, select **Custom repositories**, and fill in:
   - Repository: `https://github.com/jirutka/hass-goliash/`
   - Category: Integration
1. Click on the **⊕ Explore & download repositories** button in the bottom right corner, then search for and select **Goliash**.
1. Click on the **Download** button in the bottom right corner.
1. Restart Home Assistant.

**TIP:** You can skip steps 2–4 by opening:

[![Add jirutka/hass-goliash repository to your Home Assistant instance][my-hacs-repo-img]][my-hacs-repo]


### Manually

1. Download `goliash.zip` from the [latest release][latest-release].
1. Unpack `goliash.zip` and copy the `custom_components/goliash` directory into the `custom_components` directory of your Home Assistant installation.
1. Restart Home Assistant.


## Configuration

1. Go to **Settings > Devices & Services > Add Integration**.
1. Select **Goliash** from the list.
1. Enter your username (email) and password you use for https://app.goliash.cz or client portal of your service provider (e.g. VUSTE).
1. Select the building you want to integrate and configure the following settings:
   - **Update interval**: How often to fetch data from the API (default: 8 hours, minimum: 1 hour).
1. The integration will automatically discover all meters in the selected building.


## Supported devices

The integration supports two types of meters.


### Water meter

Measures the consumption of cold and hot water.
The ID prefix for cold water meters in Goliash is `sv-`, and for hot water meters it’s `tv-`.

This type of device exposes the following entities.

| Name                    | Platform | Category   | Description                                                          |
| ----------------------- | -------- | ---------- | -------------------------------------------------------------------- |
| consumption_total       | Sensor   |            | Total water consumption in cubic meters (m³).                        |
| last_measured           | Sensor   | Diagnostic | Timestamp of the last successful reading from the meter.             |


### Heat cost allocator

Measures heating cost units ([ITN](https://www.merenionline.cz/index.php/mereni-tepla/indikatory-topnych-nakladu) in Czech).
The ID prefix in Goliash is `itn-`.

This type of device exposes the following entities.

| Name                    | Platform | Category   | Description                                                          |
| ----------------------- | -------- | ---------- | -------------------------------------------------------------------- |
| cost_units_total        | Sensor   |            | Total heating cost units.                                            |
| last_measured           | Sensor   | Diagnostic | Timestamp of the last successful reading from the meter.             |


## License

This project is licensed under the [MIT License].

[releases]: https://github.com/jirutka/hass-goliash/releases
[latest-release]: https://github.com/jirutka/hass-goliash/releases/latest
[releases-shield]: https://img.shields.io/github/release/jirutka/hass-goliash.svg?style=flat-square
[issues]: https://github.com/jirutka/hass-goliash/issues
[HACS]: https://hacs.xyz/
[my-hacs-repo]: https://my.home-assistant.io/redirect/hacs_repository/?owner=jirutka&repository=hass-goliash&category=Integration
[my-hacs-repo-img]: https://my.home-assistant.io/badges/hacs_repository.svg
[MIT License]: https://opensource.org/license/MIT
