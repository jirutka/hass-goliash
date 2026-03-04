# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
"""Goliash API client."""

import logging
from datetime import date
from typing import TypeVar

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pydantic import BaseModel, ValidationError

from ..const import GOLIASH_API_BASE_URL, HTTP_TIMEOUT
from .models import (
    Building,
    Device,
    DeviceDetailResponse,
    LoginResponse,
    SubStructuresResponse,
    UserBuildingsResponse,
)

_BaseModelT = TypeVar("_BaseModelT", bound=BaseModel)

_LOGGER = logging.getLogger(__name__)

_LOGIN_ENDPOINT = "/login_check"
_STRUCTURE_ENDPOINT = "/structure/user-buildings"
_SUBSTRUCTURES_ENDPOINT = "/structure/sub-structures/{building_id}"
_DEVICE_DETAIL_ENDPOINT = "/device/detail/{device_id}"


class GoliashAuthError(Exception):
    """Authentication error from Goliash API."""


class GoliashInvalidDataError(Exception):
    """Goliash API response body fails Pydantic model validation."""

    def __init__(self, message: str, cause: ValidationError):
        super().__init__(f"{message}: {cause}")
        self.__cause__ = cause


class GoliashApi:
    """Goliash API client."""

    _username: str
    _password: str
    _token: str | None
    _hass: HomeAssistant

    def __init__(self, hass: HomeAssistant, username: str, password: str) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._username = username
        self._password = password
        self._token = None

    async def authenticate(self) -> None:
        """Authenticate with the API and store the token."""
        # JWT tokens typically don't have expiration in the response,
        # so we'll refresh on each update cycle to be safe
        try:
            model = await self._fetch_and_validate(
                method="POST",
                path=_LOGIN_ENDPOINT,
                json={"username": self._username, "password": self._password},
                authenticate=False,
                model_class=LoginResponse,
            )
            self._token = model.token
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise GoliashAuthError("Invalid username or password") from err
            raise

    async def get_buildings(self) -> dict[int, Building]:
        """Get list of buildings available to the user."""
        model = await self._fetch_and_validate(
            _STRUCTURE_ENDPOINT, UserBuildingsResponse
        )
        return {ub.structure.id: ub.structure for ub in model.buildings}

    async def get_devices(self, building_id: int) -> dict[int, Device]:
        """Get devices for a specific building."""
        endpoint = _SUBSTRUCTURES_ENDPOINT.format(building_id=building_id)
        model = await self._fetch_and_validate(endpoint, SubStructuresResponse)
        # Extract all devices from all structures (flats)
        devices: dict[int, Device] = {}
        for structure in model.structures:
            for device in structure.structure.devices:
                devices[device.id] = device
        return devices

    async def get_device_detail(
        self,
        device_id: int,
        from_date: date,
        to_date: date | None = None,
        cumulative: bool = True,
    ) -> DeviceDetailResponse:
        """Get device measurements (readings) for a specific device within a date(time) range.

        If `cumulative` is True, the readings contain total cumulative consumption instead of daily
        consumption.
        """
        assert to_date is None or type(from_date) is type(to_date)
        assert to_date is None or from_date < to_date

        endpoint = _DEVICE_DETAIL_ENDPOINT.format(device_id=device_id)
        url = f"{endpoint}?from={from_date.isoformat()}&showMeasurements={str(cumulative).lower()}"
        if to_date:
            url += f"&to={to_date.isoformat()}"

        return await self._fetch_and_validate(url, DeviceDetailResponse)

    async def _fetch_and_validate(
        self,
        path: str,
        model_class: type[_BaseModelT],
        method: str = "GET",
        json: object = None,
        authenticate: bool = True,
    ) -> _BaseModelT:
        """Fetch JSON data and validate it with Pydantic model."""
        if authenticate and self._token is None:
            await self.authenticate()

        session = async_get_clientsession(self._hass)
        url = f"{GOLIASH_API_BASE_URL}{path}"
        headers = {"Accept": "application/json"}
        if authenticate:
            headers["Authorization"] = f"Bearer {self._token}"

        _LOGGER.debug("Sending GET %s", url)
        try:
            async with session.request(
                method, url, headers=headers, json=json, timeout=HTTP_TIMEOUT
            ) as resp:
                _LOGGER.debug(
                    "Received response from %s: HTTP %s\n%s",
                    url,
                    resp.status,
                    await resp.text(),
                )
                resp.raise_for_status()
                data = await resp.json()  # pyright: ignore[reportAny]
                return model_class.model_validate(data)
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching data from %s: %s", url, err)
            raise
        except ValidationError as err:
            _LOGGER.error("Invalid response body from %s: %s", url, err)
            raise GoliashInvalidDataError(f"Invalid response body from {path}", err)
