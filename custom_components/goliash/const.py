# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
from datetime import timedelta
from typing import Final

from aiohttp.client import ClientTimeout

DOMAIN: Final = "goliash"

ISSUES_URL: Final = "https://github.com/jirutka/hass-goliash/issues"
"""URL where to report issues."""

GOLIASH_API_BASE_URL: Final = "https://api.goliash.cz/api"
"""Base URL of the Goliash API (without trailing slash)."""

HTTP_TIMEOUT: Final = ClientTimeout(total=10)
"""Timeout in seconds for HTTP requests."""

UPDATE_INTERVAL_DEFAULT: Final = timedelta(hours=8)
"""The default data update interval."""
UPDATE_INTERVAL_MIN: Final = timedelta(hours=1)
"""The minimal data update interval the user can select in the configuration flow."""

# Config entry data keys.
CONF_BUILDING_ID: Final = "building_id"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_BACKFILL_ENABLED: Final = "backfill_enabled"
CONF_BACKFILL_SINCE: Final = "backfill_since"

# Keys used in descriptions and unique_id.
KEY_CONSUMPTION_TOTAL: Final = "consumption_total"
KEY_CONST_UNITS_TOTAL: Final = "cost_units_total"
KEY_LAST_MEASURED: Final = "last_measured"

# Measurement types (measurementTypeString in Goliash API).
MEASUREMENT_TYPE_HOT_WATER: Final = "hot"
MEASUREMENT_TYPE_COLD_WATER: Final = "cold"
MEASUREMENT_TYPE_HEATING: Final = "itn"
