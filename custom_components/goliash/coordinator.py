# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
from dataclasses import dataclass
from datetime import date, timedelta
import logging
from typing import override

from homeassistant.components.recorder.models import StatisticData
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import GoliashApi, GoliashAuthError, GoliashInvalidDataError
from .api.models import Device
from .config_flow import GoliashConfigData
from .const import DOMAIN
from .utils import deduplicate_by

# It must be in this file to avoid circular dependency.
type GoliashConfigEntry = ConfigEntry[GoliashDataCoordinator]

_LOGGER = logging.getLogger(__name__)


@dataclass
class GoliashData:
    devices: dict[int, Device]


class GoliashDataCoordinator(DataUpdateCoordinator[GoliashData]):
    _api: GoliashApi
    _config: GoliashConfigData

    # Callback listeners only when data has changed.
    # @override
    always_update = False

    def __init__(self, hass: HomeAssistant, entry: GoliashConfigEntry) -> None:
        self._config = config = GoliashConfigData(**entry.data)  # pyright: ignore[reportAny]
        self._api = GoliashApi(hass, config.username, config.password)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config.building_id}",
            update_interval=timedelta(seconds=config.update_interval),
            config_entry=entry,
        )

    @property
    def config(self):
        return self._config

    @override
    async def _async_update_data(self) -> GoliashData:
        """Fetch data from the API."""
        try:
            await self._api.authenticate()
            devices = await self._api.get_devices(self._config.building_id)

            return GoliashData(devices=devices)

        except GoliashAuthError as err:
            raise ConfigEntryAuthFailed from err
        except GoliashInvalidDataError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        # Note: aiohttp.ClientError is already handled by DataUpdateCoordinator.

    async def fetch_daily_statistics(
        self,
        device_id: int,
        since_date: date,
    ) -> list[StatisticData]:
        """Fetch readings for device_id from API and convert them to daily statistics."""

        _LOGGER.info(f"Fetching readings for device {device_id} since {since_date}")
        readings = await self._api.get_device_readings(device_id, since_date)
        since_time = dt_util.start_of_local_day(since_date)
        statistics = list(
            deduplicate_by(
                (
                    StatisticData(start=dt_util.start_of_local_day(time), state=value)
                    for (time, value) in sorted(readings, key=lambda x: x[0])
                    if time >= since_time
                ),
                key=lambda x: x["start"],
            )
        )
        return statistics
