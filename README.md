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

TODO


## Entities

TODO

| Name                | Platform      | Category   | Description
| ------------------- | ------------- | ---------- | --------------------------------------------------------------------------|


## Screenshots

TODO

## Resources

TODO

## License

This project is licensed under the [MIT License].


[releases]: https://github.com/jirutka/hass-goliash/releases
[latest-release]: https://github.com/jirutka/hass-goliash/releases/latest
[releases-shield]: https://img.shields.io/github/release/jirutka/hass-goliash.svg?style=flat-square
[HACS]: https://hacs.xyz/
[smarwi-website]: https://vektiva.com/index.php/en/
[smarwi-manual]: https://vektiva.com/downloads/SMARWI_manual_EN.pdf
[smarwi-api-doc]: https://vektiva.gitlab.io/vektivadocs/en/api/index.html
[my-hacs-repo]: https://my.home-assistant.io/redirect/hacs_repository/?owner=jirutka&repository=hass-goliash&category=Integration
[my-hacs-repo-img]: https://my.home-assistant.io/badges/hacs_repository.svg
[MIT License]: https://opensource.org/license/MIT
