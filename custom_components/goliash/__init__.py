# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import GoliashConfigEntry, GoliashDataCoordinator


PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: GoliashConfigEntry) -> bool:
    """Set up Goliash from a config entry."""
    entry.runtime_data = GoliashDataCoordinator(hass, entry)

    await entry.runtime_data.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.runtime_data.async_update_listeners()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GoliashConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
