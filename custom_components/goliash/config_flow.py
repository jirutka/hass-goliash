# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
from collections.abc import Mapping
import dataclasses
from dataclasses import dataclass
import logging
from typing import Any, cast, override

import aiohttp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
import voluptuous as vol

from .api import GoliashApi, GoliashAuthError, GoliashInvalidDataError
from .api.models import Building
from .const import (
    CONF_BUILDING_ID,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    ISSUES_URL,
    UPDATE_INTERVAL_DEFAULT,
    UPDATE_INTERVAL_MIN,
)

_LOGGER = logging.getLogger(__name__)

_STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


@dataclass(frozen=True)
class GoliashConfigData:
    """A typed wrapper for ConfigEntry.data."""

    # Property names must be in sync with CONF_* constants.
    username: str
    """Username (email) for Goliash API."""
    password: str
    """Password for Goliash API."""
    building_id: int
    """ID of the building for which the data is fetched."""
    update_interval: int
    """Update interval for the data update coordinator (in seconds)."""

    def asdict(self) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return dataclasses.asdict(self)


class GoliashConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goliash."""

    VERSION: int = 1
    MINOR_VERSION: int = 1

    _api: GoliashApi | None = None
    _username: str | None = None
    _password: str | None = None
    _buildings: dict[int, Building] | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = str(user_input[CONF_USERNAME])
            self._password = str(user_input[CONF_PASSWORD])
            self._api = GoliashApi(self.hass, self._username, self._password)

            # Test connection
            try:
                await self._api.authenticate()
                return await self.async_step_select_building()
            except GoliashAuthError:
                errors["base"] = "invalid_auth"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except GoliashInvalidDataError:
                return self.async_abort(
                    reason="invalid_data",
                    description_placeholders={"issues_url": ISSUES_URL},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_select_building(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Select a building and configure update interval."""

        if self._buildings is None and self._api:
            try:
                self._buildings = await self._api.get_buildings()
            except (aiohttp.ClientError, GoliashAuthError) as err:
                return self.async_abort(
                    reason="cannot_connect",
                    description_placeholders={"error": str(err)},
                )
            except GoliashInvalidDataError:
                return self.async_abort(
                    reason="invalid_data",
                    description_placeholders={"issues_url": ISSUES_URL},
                )

        if not self._buildings:
            return self.async_abort(reason="no_buildings")

        if user_input is not None:
            return await self._async_create_entry(user_input)

        return self._show_select_building_form({})

    async def _async_create_entry(
        self, user_input: dict[str, object]
    ) -> ConfigFlowResult:
        """Create config entry after validating user input."""
        assert self._buildings is not None
        assert self._username is not None
        assert self._password is not None

        building_id = int(cast(str, user_input[CONF_BUILDING_ID]))
        if not (building := self._buildings.get(building_id)):
            return self._show_select_building_form(
                {CONF_BUILDING_ID: "invalid_building"}
            )

        update_interval = cast(int, user_input[CONF_UPDATE_INTERVAL]) * 3600

        return self.async_create_entry(
            title=building.name,
            data=GoliashConfigData(
                username=self._username,
                password=self._password,
                building_id=building_id,
                update_interval=update_interval,
            ).asdict(),
        )

    def _show_select_building_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Show the select building form with errors."""
        assert self._buildings is not None

        return self.async_show_form(
            step_id="select_building",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BUILDING_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=str(b.id), label=b.name)
                                for b in self._buildings.values()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=int(UPDATE_INTERVAL_DEFAULT.total_seconds() // 3600),
                    ): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                mode=selector.NumberSelectorMode.BOX,
                                unit_of_measurement="h",
                                min=int(UPDATE_INTERVAL_MIN.total_seconds() // 3600),
                            ),
                        ),
                        vol.Range(min=int(UPDATE_INTERVAL_MIN.total_seconds() // 3600)),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, object],  # pyright: ignore[reportUnusedParameter]
    ) -> ConfigFlowResult:
        """Handle re-authentication upon an API authentication error."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication dialog."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            username = str(user_input[CONF_USERNAME])
            password = str(user_input[CONF_PASSWORD])
            api = GoliashApi(self.hass, username, password)

            # Test connection with new credentials
            try:
                await api.authenticate()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_USERNAME: username, CONF_PASSWORD: password},
                )
            except GoliashAuthError:
                errors["base"] = "invalid_auth"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except GoliashInvalidDataError:
                return self.async_abort(
                    reason="invalid_data",
                    description_placeholders={"issues_url": ISSUES_URL},
                )

        username = str(reauth_entry.data.get(CONF_USERNAME))

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=username,
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"username": username},
            errors=errors,
        )
