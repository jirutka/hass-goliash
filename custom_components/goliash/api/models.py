# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
"""Data models for Goliash API."""

from datetime import datetime
from pydantic import BaseModel, Field

########## /api/login_check ##########


class LoginResponse(BaseModel):
    """Response from /api/login_check endpoint."""

    token: str


########## /api/structure/sub-structures/{id} ##########


class LastState(BaseModel):
    """Represents the last state of a device (from /api/structure/sub-structures/{id})."""

    value: float
    last_measurement: datetime = Field(alias="lastMeasurement")
    error_state: object | None = Field(alias="errorState")
    # Omitted properties:
    # - data: dict[str, str] (contains only "rssi")


class Device(BaseModel):
    """Represents a meter device (from /api/structure/sub-structures/{id})."""

    id: int
    device_id: str = Field(alias="deviceId")
    measurement_type: str = Field(alias="measurementTypeString")
    lastState: LastState = Field(alias="lastState")
    manufacturer: dict[str, str] | None

    @property
    def last_value(self) -> float:
        """Return the last measured value.

        WARNING: This is sometimes delayed be several hours!
        """
        return self.lastState.value

    @property
    def last_measured(self) -> datetime:
        """Return the last measurement timestamp.

        WARNING: This is sometimes delayed be several hours!
        """
        return self.lastState.last_measurement

    @property
    def error_state(self) -> str | None:
        if state := self.lastState.error_state:
            return str(state)

    @property
    def manufacturer_name(self) -> str | None:
        """Return the manufacturer name."""
        if self.manufacturer is not None:
            return self.manufacturer.get("name")


class Flat(BaseModel):
    """Represents a flat (from /api/structure/sub-structures/{id})."""

    id: int
    custom_name: str | None = Field(alias="customName")
    flat_number: int | None = Field(alias="flatNumber")
    floor_number: int | None = Field(alias="floorNumber")
    description: str | None
    devices: list[Device]


class SubStructure(BaseModel):
    """Represents ??? (from /api/structure/sub-structures/{id})."""

    structure: Flat

    # Omitted properties:
    # - canEditDeviceSettings: boolean
    # - canExportDevice: boolean
    # - canShowAccesses: boolean,
    # - canEditAccesses: boolean
    # - canSubscribeMonthlyReports: boolean


class SubStructuresResponse(BaseModel):
    """Response from /api/structure/sub-structures/{id} endpoint."""

    structures: list[SubStructure]

    # Omitted properties:
    # - address: { addressLine: str, cityLine: str }
    # - masterDevices: []


########## /api/structure/user-buildings ##########


class Building(BaseModel):
    """Represents a building structure (from /api/structure/user-buildings)."""

    id: int
    custom_name: str | None = Field(default=None, alias="customName")
    type: str
    address: dict[str, str]

    # Omitted properties:
    # - portal: { id: int, name: str }

    @property
    def name(self) -> str:
        """Return the building name, using custom_name, address or default."""
        if self.custom_name:
            return self.custom_name
        try:
            return f"{self.address["addressLine"]}, {self.address["cityLine"]}"
        except KeyError:
            return f"{self.type.capitalize() or "Building"} {self.id}"


class UserBuilding(BaseModel):
    """Represents a building available to the user (from /api/structure/user-buildings)."""

    structure: Building

    # Omitted properties:
    # - canExportAll: boolean
    # - canSubscribeMonthlyReports: boolean


class UserBuildingsResponse(BaseModel):
    """Response from /api/structure/user-buildings endpoint."""

    buildings: list[UserBuilding]


########## /api/device/detail/{id} ##########


class Reading(BaseModel):
    """Represents a single reading (measurement) (from /api/device/detail/{id})."""

    date: datetime
    value: float


class DeviceGraphData(BaseModel):
    """Represents graph data (from /api/device/detail/{id})."""

    current_state: float = Field(alias="currentState")
    measures: list[Reading]

    # Omitted properties:
    # - type: "elevation"
    # - currentState: float
    # - dataFrom: datetime
    # - dataTo: datetime
    # - backflow_detected: bool


class DeviceDetailResponse(BaseModel):
    """Response from /api/device/detail/{id} endpoint."""

    graph_data: DeviceGraphData = Field(alias="graphData")

    # Omitted properties:
    # - device: { deviceId, manufacturer, measurementTypeString }
    # - errors: []
    # - enable: list[str]
    # - consumption: float

    @property
    def readings(self) -> list[Reading]:
        """Return readings sorted by date."""
        # API returns measures already sorted.
        return self.graph_data.measures
