# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Jakub Jirutka <jakub@jirutka.cz>
from collections.abc import Iterable
from datetime import datetime
from typing import Callable, Literal, TypeVar

from homeassistant.components.recorder.core import StatisticData
from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    get_last_statistics,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.recorder import get_instance as get_recorder_instance
from homeassistant.util import dt as dt_util

T = TypeVar("T")


def deduplicate_by(items: Iterable[T], key: Callable[[T], object]) -> Iterable[T]:
    """Remove duplicate items from an iterable based on a key function.

    Preserves the first occurrence of each unique key.
    """
    seen: set[object] = set()
    return (item for item in items if (k := key(item)) not in seen and not seen.add(k))


def datetime_fromtimestamp(timestamp: float) -> datetime:
    """Convert a Unix timestamp to a datetime object in the default time zone."""
    return datetime.fromtimestamp(timestamp, tz=dt_util.get_default_time_zone())


def inject_cumulative_sum(statistics: list[StatisticData], init_sum: float) -> None:
    """Modifies the input statistics list in-place by adding a "sum" key to each item.

    Handles sensors that generally increase but can reset (e.g., to 0 or a lower value).
    When a reset is detected (current value < previous value), the cumulative sum
    continues from where it left off by adding the current value to the running total.
    """
    sum = init_sum
    prev_state = init_sum
    for data in statistics:
        assert (state := data.get("state")) is not None
        if state < prev_state:
            # Reset detected - add the current value (it started from 0 again).
            sum += state
        else:
            # Normal increase - add the difference.
            sum += state - prev_state
        data["sum"] = sum
        prev_state = state


async def get_last_statistic(
    hass: HomeAssistant,
    statistic_id: str,
    convert_units: bool,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]],
) -> StatisticsRow | None:
    """Retrieve the last statistic value for a given statistic ID."""
    recorder = get_recorder_instance(hass)

    stats = await recorder.async_add_executor_job(
        get_last_statistics,
        hass,
        1,
        statistic_id,
        convert_units,
        types,
    )
    if not stats or statistic_id not in stats:
        return

    return stats[statistic_id][0]
