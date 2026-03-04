# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
class ReadingData:
    cumulative_total: float
    last_measured: datetime | None


@dataclass
class GoliashData:
    devices: list[Device]
    readings: dict[int, ReadingData]
    """Readings per device ID."""


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
    def config(self) -> GoliashConfigData:
        return self._config

    @override
    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup."""
        try:
            await self._api.authenticate()
            devices = await self._api.get_devices(self._config.building_id)
            readings = {
                dev.id: await self._fetch_last_reading(dev.id) for dev in devices
            }
            self.data = GoliashData(devices=devices, readings=readings)

        except GoliashAuthError as err:
            raise ConfigEntryAuthFailed from err
        except GoliashInvalidDataError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        # Note: aiohttp.ClientError is already handled by DataUpdateCoordinator.

    @override
    async def _async_update_data(self) -> GoliashData:
        """Fetch data from the API."""
        # Device IDs from the active entities. This is used to avoid updating
        # data for devices that are disabled.
        device_ids = set[int](self.async_contexts())

        try:
            await self._api.authenticate()
            readings = {id: await self._fetch_last_reading(id) for id in device_ids}

            return GoliashData(devices=self.data.devices, readings=readings)

        except GoliashAuthError as err:
            raise ConfigEntryAuthFailed from err
        except GoliashInvalidDataError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        # Note: aiohttp.ClientError is already handled by DataUpdateCoordinator.

    async def _fetch_last_reading(self, device_id: int) -> ReadingData:
        since_date = date.today() - timedelta(days=7)

        device = await self._api.get_device_detail(device_id, since_date)
        last_measured = device.readings[-1].date if len(device.readings) > 0 else None

        return ReadingData(
            cumulative_total=device.last_total, last_measured=last_measured
        )

    async def fetch_daily_statistics(
        self,
        device_id: int,
        since_date: date,
    ) -> list[StatisticData]:
        """Fetch readings for device_id from API and convert them to daily statistics."""

        _LOGGER.info(f"Fetching readings for device {device_id} since {since_date}")
        device = await self._api.get_device_detail(device_id, since_date)
        statistics = list(
            deduplicate_by(
                (
                    StatisticData(
                        start=dt_util.start_of_local_day(r.date), state=r.value
                    )
                    for r in device.readings
                ),
                key=lambda x: x["start"],
            )
        )
        return statistics
