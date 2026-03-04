# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from math import floor
from typing import Callable, cast, override

from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.core import StatisticMetaData
from homeassistant.components.recorder.db_schema import StatisticsShortTerm
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
from homeassistant.helpers.recorder import get_instance as get_recorder_instance
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import VolumeConverter

from .const import (
    KEY_CONST_UNITS_TOTAL,
    KEY_CONSUMPTION_TOTAL,
    KEY_LAST_MEASURED,
    MEASUREMENT_TYPE_COLD_WATER,
    MEASUREMENT_TYPE_HOT_WATER,
    MEASUREMENT_TYPE_HEATING,
)
from .coordinator import ReadingData, GoliashConfigEntry
from .entity import GoliashDeviceEntity
from .utils import datetime_fromtimestamp, get_last_statistic, inject_cumulative_sum

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GoliashSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[ReadingData], StateType | date | datetime]
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
        value_fn=lambda data: data.cumulative_total,
    ),
    MEASUREMENT_TYPE_COLD_WATER: GoliashSensorEntityDescription(
        key=KEY_CONSUMPTION_TOTAL,
        icon="mdi:water",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_class=VolumeConverter.UNIT_CLASS,
        value_fn=lambda data: data.cumulative_total,
    ),
    MEASUREMENT_TYPE_HEATING: GoliashSensorEntityDescription(
        key=KEY_CONST_UNITS_TOTAL,
        icon="mdi:radiator",
        suggested_display_precision=0,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_class="unitless",
        value_fn=lambda data: data.cumulative_total,
    ),
}

_LAST_MEASURED_SENSOR = GoliashSensorEntityDescription(
    key=KEY_LAST_MEASURED,
    icon="mdi:clock",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    native_unit_of_measurement=None,
    value_fn=lambda data: data.last_measured,
)


async def async_setup_entry(
    hass: HomeAssistant,  # pyright: ignore[reportUnusedParameter]
    entry: GoliashConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    entities: list[GoliashBaseSensor] = []
    for device in coordinator.data.devices:
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
            GoliashBaseSensor(
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
            and self.device.id in self.coordinator.data.readings
        )

    @override
    def _handle_coordinator_update(self) -> None:
        description = cast(GoliashSensorEntityDescription, self.entity_description)

        if data := self.coordinator.data.readings.get(self.device.id):
            self._attr_native_value = description.value_fn(data)
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
        if not data:
            return
        inject_cumulative_sum(data, last_sum)

        _LOGGER.warning(
            f"{self.entity_id}: Backfilling {len(data)} daily statistics since {since_date} (last sum was {last_sum})"
        )
        # XXX: Import a short-term statistic entry to prime the recorder with the cumulative sum.
        #  This ensures that when Home Assistant's recorder automatically begins tracking this
        #  entity's state, it will correctly use the cumulative sum rather than calculating a new
        #  sum from individual state changes. This is a hack that uses an internal API, but I don't
        #  know any better way.
        last_stat = data[-1].copy()
        time = datetime.today() - timedelta(minutes=10)
        last_stat["start"] = time.replace(
            minute=floor(time.minute / 5) * 5, second=0, microsecond=0
        )
        get_recorder_instance(self.hass).async_import_statistics(
            self.statistic_metadata, [last_stat], StatisticsShortTerm
        )

        # Now import historical statistics.
        # XXX: We use async_import_statistics() instead of async_add_external_statistics()
        #  because these statistics belong to a specific sensor entity (statistic_id = entity_id).
        #  The async_add_external_statistics() function does not allow statistic_id to be a
        #  valid entity_id, so the statistics are not linked to the sensor. Even if we accept that
        #  historical statistics are separate, HASS would still record statistics from state
        #  changes, causing data duplication.
        async_import_statistics(self.hass, self.statistic_metadata, data)
