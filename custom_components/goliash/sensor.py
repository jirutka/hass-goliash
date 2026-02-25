# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Callable, cast, override

from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.core import StatisticMetaData
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import VolumeConverter

from .api.models import Device
from .const import (
    KEY_CONST_UNITS_TOTAL,
    KEY_CONSUMPTION_TOTAL,
    KEY_LAST_MEASURED,
    MEASUREMENT_TYPE_COLD_WATER,
    MEASUREMENT_TYPE_HOT_WATER,
    MEASUREMENT_TYPE_HEATING,
)
from .coordinator import GoliashConfigEntry
from .entity import GoliashDeviceEntity
from .utils import datetime_fromtimestamp, get_last_statistic, inject_cumulative_sum

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GoliashSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[Device], StateType | date | datetime]
    # Fields from StatisticMetaData.
    mean_type: StatisticMeanType = StatisticMeanType.NONE
    has_sum: bool = True
    unit_class: str | None = None


_MEASUREMENT_SENSORS = {
    MEASUREMENT_TYPE_HOT_WATER: GoliashSensorEntityDescription(
        key=KEY_CONSUMPTION_TOTAL,
        icon="mdi:water-thermometer",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_class=VolumeConverter.UNIT_CLASS,
        value_fn=lambda dev: dev.last_value,
    ),
    MEASUREMENT_TYPE_COLD_WATER: GoliashSensorEntityDescription(
        key=KEY_CONSUMPTION_TOTAL,
        icon="mdi:water",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_class=VolumeConverter.UNIT_CLASS,
        value_fn=lambda dev: dev.last_value,
    ),
    MEASUREMENT_TYPE_HEATING: GoliashSensorEntityDescription(
        key=KEY_CONST_UNITS_TOTAL,
        icon="mdi:radiator",
        suggested_display_precision=0,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_class="unitless",
        value_fn=lambda dev: dev.last_value,
    ),
}

_LAST_MEASURED_SENSOR = GoliashSensorEntityDescription(
    key=KEY_LAST_MEASURED,
    icon="mdi:clock",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    native_unit_of_measurement=None,
    value_fn=lambda dev: dev.last_measured,
)


async def async_setup_entry(
    hass: HomeAssistant,  # pyright: ignore[reportUnusedParameter]
    entry: GoliashConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    entities: list[GoliashStatisticSensor] = []
    for device in coordinator.data.devices.values():
        # Create separate entity for each measurement type
        if device.measurement_type in _MEASUREMENT_SENSORS:
            entities.append(
                GoliashStatisticSensor(
                    coordinator,
                    device,
                    _MEASUREMENT_SENSORS[device.measurement_type],
                )
            )
        entities.append(
            GoliashStatisticSensor(
                coordinator,
                device,
                _LAST_MEASURED_SENSOR,
            )
        )
    async_add_entities(entities)


class GoliashBaseSensor(GoliashDeviceEntity, SensorEntity):
    """
    Base class for Goliash sensors.
    """

    @property
    @override
    def available(self) -> bool:  # pyright: ignore[reportIncompatibleVariableOverride]
        return (
            self.coordinator.last_update_success
            and self.device.id in self.coordinator.data.devices
        )

    @override
    def _handle_coordinator_update(self) -> None:
        description = cast(GoliashSensorEntityDescription, self.entity_description)

        if device := self.coordinator.data.devices.get(self.device.id):
            self._attr_native_value = description.value_fn(device)
        return super()._handle_coordinator_update()


class GoliashStatisticSensor(GoliashBaseSensor):
    """
    Sensor entity that supports backfilling of historical statistics to the Recorder.
    """

    @property
    def statistic_metadata(self) -> StatisticMetaData:
        description = cast(GoliashSensorEntityDescription, self.entity_description)
        return StatisticMetaData(
            statistic_id=self.entity_id,
            source=RECORDER_DOMAIN,
            name=None,
            has_sum=True,
            mean_type=description.mean_type,
            unit_class=description.unit_class,
            unit_of_measurement=description.native_unit_of_measurement,
        )

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.coordinator.config.backfill_enabled:
            try:
                await self._backfill_statistics()
            except Exception as err:
                _LOGGER.error(f"{self.entity_id}: Failed to backfill statistics")
                _LOGGER.exception(err)

    async def _backfill_statistics(self) -> None:
        since_date = date.fromisoformat(self.coordinator.config.backfill_since)
        last_sum = 0
        if stat := await get_last_statistic(self.hass, self.entity_id, True, {"sum"}):
            assert (start := stat.get("start"))
            last_time = datetime_fromtimestamp(start)
            _LOGGER.debug(f"{self.entity_id}: Last statistic data is from {last_time}")

            since_date = last_time.date() + timedelta(days=1)
            if since_date > date.today():
                return
            last_sum = stat.get("sum") or 0.0

        data = await self.coordinator.fetch_daily_statistics(self.device.id, since_date)
        inject_cumulative_sum(data, last_sum)

        _LOGGER.warning(
            f"{self.entity_id}: Backfilling daily statistics since {since_date} (last sum is {last_sum})"
        )
        async_import_statistics(self.hass, self.statistic_metadata, data)
