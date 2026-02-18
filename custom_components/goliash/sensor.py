# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import Device
from .const import (
    KEY_CONST_UNITS_TOTAL,
    KEY_CONSUMPTION_TOTAL,
    KEY_LAST_MEASURED,
    MEASUREMENT_TYPE_COLD_WATER,
    MEASUREMENT_TYPE_HOT_WATER,
    MEASUREMENT_TYPE_HEATING,
)
from .coordinator import GoliashConfigEntry, GoliashDataCoordinator
from .entity import GoliashDeviceEntity

_MEASUREMENT_SENSORS = {
    MEASUREMENT_TYPE_HOT_WATER: SensorEntityDescription(
        key=KEY_CONSUMPTION_TOTAL,
        icon="mdi:water-thermometer",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MEASUREMENT_TYPE_COLD_WATER: SensorEntityDescription(
        key=KEY_CONSUMPTION_TOTAL,
        icon="mdi:water",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MEASUREMENT_TYPE_HEATING: SensorEntityDescription(
        key=KEY_CONST_UNITS_TOTAL,
        icon="mdi:radiator",
        suggested_display_precision=0,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
}

_LAST_MEASURED_SENSOR = SensorEntityDescription(
    key=KEY_LAST_MEASURED,
    icon="mdi:clock",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    native_unit_of_measurement=None,
)


async def async_setup_entry(
    hass: HomeAssistant,  # pyright: ignore[reportUnusedParameter]
    entry: GoliashConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    entities: list[GoliashSensor] = []
    for device in coordinator.data.devices.values():
        # Create separate entity for each measurement type
        if device.measurement_type in _MEASUREMENT_SENSORS:
            entities.append(
                GoliashSensor(
                    coordinator,
                    device,
                    _MEASUREMENT_SENSORS[device.measurement_type],
                )
            )
        entities.append(
            GoliashSensor(
                coordinator,
                device,
                _LAST_MEASURED_SENSOR,
            )
        )
    async_add_entities(entities)


class GoliashSensor(GoliashDeviceEntity, SensorEntity):
    def __init__(
        self,
        coordinator: GoliashDataCoordinator,
        device: Device,
        entity_description: SensorEntityDescription,
    ) -> None:
        self.entity_description = entity_description
        super().__init__(coordinator, device)

    @property
    @override
    def available(self) -> bool:  # pyright: ignore[reportIncompatibleVariableOverride]
        return (
            self.coordinator.last_update_success
            and self.device.id in self.coordinator.data.devices
        )

    @override
    def _handle_coordinator_update(self) -> None:
        if device := self.coordinator.data.devices.get(self.device.id):
            if self.entity_description.key == KEY_LAST_MEASURED:
                self._attr_native_value = device.last_measured
            else:
                self._attr_native_value = device.last_value
        return super()._handle_coordinator_update()
