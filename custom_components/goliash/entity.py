# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
from typing import override

from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import GoliashDataCoordinator
from .api.models import Device


class GoliashDeviceEntity(CoordinatorEntity[GoliashDataCoordinator]):
    """Base implementation for Goliash meter device."""

    device: Device
    # @override
    coordinator: GoliashDataCoordinator

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GoliashDataCoordinator,
        device: Device,
        entity_description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)

        if entity_description and not self.translation_key:
            self._attr_translation_key = entity_description.key

        assert self.translation_key is not None, "translation_key is not set"

        self.device = device
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_id,
            manufacturer=device.manufacturer_name,
            model=self._device_name(device.measurement_type),
        )
        self._attr_unique_id = (
            f"{slugify(self.device.device_id)}_{self.suggested_object_id}"
        )

    @property
    @override
    def suggested_object_id(self) -> str | None:
        return self.entity_description.key

    def _device_name(self, key: str) -> str:
        hass: HomeAssistant = self.coordinator.hass  # pyright: ignore[reportAny]
        language: str = hass.config.language  # pyright: ignore[reportAny]
        full_translation_key = f"component.{DOMAIN}.device.{key}.name"

        translations = translation.async_get_cached_translations(
            hass, language, "device", DOMAIN
        )
        return translations.get(full_translation_key, key)
