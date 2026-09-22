"""Typed result contracts local to the hardware adapter boundary."""

from typing import TypedDict


class DHT22Reading(TypedDict):
    temperature: float | None
    humidity_air: float | None
    error: str | None


class SoilReading(TypedDict):
    soil_humidity: float | None
    soil_raw: int | None
    error: str | None


class TankReading(TypedDict):
    distance_cm: float
    water_level_cm: float
    water_pct: float
    error: str | None


class PumpResult(TypedDict):
    pump: bool
    message: str
