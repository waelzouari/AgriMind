"""Map internal sensor snapshots to the versioned telemetry wire contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from agrimind_edge.contracts.enums import TelemetryMetric, TelemetryQuality
from agrimind_edge.contracts.models import Telemetry
from agrimind_edge.domain.sensors import Measurement, ReadingQuality, SensorSnapshot


@dataclass(frozen=True, slots=True)
class TelemetryMappingResult:
    telemetry: tuple[Telemetry, ...]
    skipped_unavailable: int


class TelemetryMapper:
    def __init__(
        self,
        farm_id: UUID,
        device_id: UUID,
        *,
        message_id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self._farm_id = farm_id
        self._device_id = device_id
        self._message_id_factory = message_id_factory or uuid4

    def map_snapshot(self, snapshot: SensorSnapshot) -> TelemetryMappingResult:
        mapped: list[Telemetry] = []
        unavailable = 0
        for metric, measurement in (
            (TelemetryMetric.TEMPERATURE, snapshot.temperature),
            (TelemetryMetric.HUMIDITY, snapshot.air_humidity),
            (TelemetryMetric.SOIL_MOISTURE, snapshot.soil_humidity),
            (TelemetryMetric.TANK_LEVEL, snapshot.tank_water_level),
        ):
            telemetry = self._map_measurement(metric, measurement)
            if telemetry is None:
                unavailable += 1
            else:
                mapped.append(telemetry)
        return TelemetryMappingResult(tuple(mapped), unavailable)

    def _map_measurement(
        self,
        metric: TelemetryMetric,
        measurement: Measurement,
    ) -> Telemetry | None:
        if measurement.quality not in {ReadingQuality.VALID, ReadingQuality.STALE}:
            return None
        if measurement.value is None or measurement.observed_at is None:
            return None
        quality = (
            TelemetryQuality.VALID
            if measurement.quality is ReadingQuality.VALID
            else TelemetryQuality.ESTIMATED
        )
        return Telemetry(
            message_id=self._message_id_factory(),
            farm_id=self._farm_id,
            device_id=self._device_id,
            metric=metric,
            value=float(measurement.value),
            unit={
                TelemetryMetric.TEMPERATURE: "°C",
                TelemetryMetric.HUMIDITY: "%",
                TelemetryMetric.SOIL_MOISTURE: "%",
                TelemetryMetric.TANK_LEVEL: "cm",
            }[metric],
            recorded_at=measurement.observed_at,
            quality=quality,
        )
