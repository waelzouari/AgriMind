"""AGM-026 deterministic P0 journeys across the existing application boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from agrimind_ingestion.application.acknowledgements import IngestionAcknowledgementFactory
from agrimind_ingestion.application.ingestion import IngestionService
from agrimind_ingestion.contracts import ContractValidator
from agrimind_ingestion.domain import DeviceRegistration, IngestionOutcome

from agrimind_edge.adapters.fake import FakeMqttTransport, FakePump, FakeScheduler
from agrimind_edge.adapters.ml import PortableTreeModelAdapter
from agrimind_edge.adapters.persistence import SqliteEventOutboxStore
from agrimind_edge.application.automatic_irrigation import (
    AutomaticIrrigationService,
    IndependentAutomaticSafetyGate,
)
from agrimind_edge.application.ingestion_acknowledgements import (
    IngestionAcknowledgementProcessor,
)
from agrimind_edge.application.irrigation_inference import IrrigationInferenceService
from agrimind_edge.application.mqtt_commands import (
    MqttAcknowledgementPublisher,
    MqttPumpCommandProcessor,
)
from agrimind_edge.application.outbox_service import OutboxService
from agrimind_edge.application.pump_command_handler import PumpCommandHandler
from agrimind_edge.application.pump_controller import SafePumpController
from agrimind_edge.config import AutomaticIrrigationConfig, InferenceConfig, PumpSafetyConfig
from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand, TopicBuilder
from agrimind_edge.contracts.enums import AcknowledgementStatus, PumpAction
from agrimind_edge.domain import (
    AutomaticSafetyReason,
    Measurement,
    PumpState,
    ReadingQuality,
    SensorError,
    SensorErrorCode,
    SensorSnapshot,
)
from agrimind_edge.domain.mqtt import MqttPublication, ReceivedMqttMessage
from agrimind_edge.domain.persistence import EdgeEvent, EnqueueResult

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts" / "v1"
NOW = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
COMMAND_ID = UUID("33333333-3333-4333-8333-333333333333")
ACK_ID = UUID("44444444-4444-4444-8444-444444444444")
REQUESTER_ID = UUID("55555555-5555-4555-8555-555555555555")


class FixedClock:
    def now_utc(self) -> datetime:
        return NOW


class FixedSnapshots:
    def __init__(self, value: SensorSnapshot) -> None:
        self.value = value

    def capture(self) -> SensorSnapshot:
        return self.value


class RegisteredDevice:
    def get(self, device_id: UUID) -> DeviceRegistration | None:
        if device_id != DEVICE_ID:
            return None
        return DeviceRegistration(DEVICE_ID, FARM_ID, "p0-fake-edge", True)

    def create(self, registration: DeviceRegistration) -> DeviceRegistration:
        raise AssertionError("provisioning is outside the P0 ingestion journey")

    def update(
        self,
        device_id: UUID,
        *,
        is_active: bool | None = None,
        label: str | None = None,
        update_label: bool = False,
    ) -> DeviceRegistration:
        raise AssertionError("provisioning is outside the P0 ingestion journey")

    def farm_exists(self, farm_id: UUID) -> bool:
        return farm_id == FARM_ID


class IdempotentPersistence:
    """Minimal trusted boundary that preserves ingestion idempotency semantics."""

    def __init__(self) -> None:
        self.acknowledgements: dict[str, dict[str, Any]] = {}

    def ingest_command_acknowledgement(self, payload: dict[str, Any]) -> str:
        identity = str(payload["acknowledgement_id"])
        previous = self.acknowledgements.get(identity)
        if previous is not None:
            return "duplicate"
        self.acknowledgements[identity] = payload
        return "inserted"

    def ingest_telemetry(self, payload: dict[str, Any]) -> str:
        raise AssertionError("telemetry is outside this acknowledgement journey")

    def ingest_device_status(self, payload: dict[str, Any]) -> str:
        raise AssertionError("device status is outside this acknowledgement journey")

    def ingest_irrigation_result(self, payload: dict[str, Any]) -> str:
        raise AssertionError("agronomic feedback is distinct from the technical ACK lifecycle")


def _measurement(
    value: float | int | None,
    unit: str,
    *,
    quality: ReadingQuality = ReadingQuality.VALID,
    observed_at: datetime | None = NOW,
) -> Measurement:
    error = None
    if quality is not ReadingQuality.VALID:
        error = SensorError(SensorErrorCode.INVALID_READING, "deterministic stale reading")
    return Measurement(value, unit, quality, observed_at, error)


def _snapshot(*, stale: bool = False) -> SensorSnapshot:
    quality = ReadingQuality.STALE if stale else ReadingQuality.VALID
    observed_at = NOW - timedelta(seconds=31) if stale else NOW
    return SensorSnapshot(
        captured_at=NOW,
        correlation_id="agm-026-cycle",
        temperature=_measurement(20.0, "celsius", quality=quality, observed_at=observed_at),
        air_humidity=_measurement(60.0, "percent", quality=quality, observed_at=observed_at),
        soil_humidity=_measurement(45.0, "percent", quality=quality, observed_at=observed_at),
        soil_raw=_measurement(20_000, "adc_raw"),
        tank_distance=_measurement(8.0, "centimeter"),
        tank_water_level=_measurement(20.0, "centimeter"),
        tank_water_percent=_measurement(50.0, "percent"),
    )


def _outbox(
    tmp_path: Path, transport: FakeMqttTransport
) -> tuple[SqliteEventOutboxStore, OutboxService]:
    store = SqliteEventOutboxStore(tmp_path / "p0.sqlite3")
    service = OutboxService(
        store,
        transport,
        clock=lambda: NOW,
        drain_submitter=lambda callback: callback(),
    )
    assert service.initialize() is True
    return store, service


def _publication(topics: TopicBuilder, acknowledgement: CommandAcknowledgement) -> MqttPublication:
    return MqttPublication(
        topics.acknowledgement(acknowledgement.command_id),
        acknowledgement.to_json(),
        1,
        False,
    )


def _cloud_ingestion() -> tuple[IngestionService, IdempotentPersistence]:
    persistence = IdempotentPersistence()
    return (
        IngestionService(
            ContractValidator(CONTRACTS),
            RegisteredDevice(),
            persistence,
            clock=lambda: NOW,
        ),
        persistence,
    )


def _apply_cloud_receipt(
    result: Any,
    store: SqliteEventOutboxStore,
    topics: TopicBuilder,
) -> None:
    receipt = IngestionAcknowledgementFactory(clock=lambda: NOW).create(result)
    assert receipt is not None
    IngestionAcknowledgementProcessor(store, topics).process(
        ReceivedMqttMessage(receipt.topic, receipt.payload.encode(), receipt.qos, receipt.retain)
    )


def test_ai_happy_path_reaches_cloud_confirmation_without_physical_hardware(
    tmp_path: Path,
) -> None:
    topics = TopicBuilder(FARM_ID, DEVICE_ID)
    transport = FakeMqttTransport()
    transport.connect()
    store, outbox = _outbox(tmp_path, transport)
    publisher = MqttAcknowledgementPublisher(transport, topics, durable_publisher=outbox)
    pump = FakePump()
    controller = SafePumpController(pump, FakeScheduler())
    handler = PumpCommandHandler(
        controller,
        PumpSafetyConfig(FARM_ID, DEVICE_ID, 120),
        clock=lambda: NOW,
        acknowledgement_id_factory=lambda: ACK_ID,
        lifecycle_sink=publisher.publish,
    )
    config = AutomaticIrrigationConfig(True, duration_seconds=10, cooldown_seconds=60)
    clock = FixedClock()
    app = AutomaticIrrigationService(
        FixedSnapshots(_snapshot()),
        IrrigationInferenceService(
            PortableTreeModelAdapter(), InferenceConfig(max_age_seconds=30), clock=lambda: NOW
        ),
        IndependentAutomaticSafetyGate(
            config, InferenceConfig(max_age_seconds=30), controller, clock
        ),
        handler,
        config,
        clock,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        command_id_factory=lambda: COMMAND_ID,
    )

    result = app.evaluate_once()

    acknowledgement = result.command_acknowledgement
    assert result.safety_decision.reason_code is AutomaticSafetyReason.ALLOWED
    assert acknowledgement is not None
    assert acknowledgement.status is AcknowledgementStatus.ACCEPTED
    assert controller.state is PumpState.RUNNING
    assert pump.active is True
    assert transport.publications == [_publication(topics, acknowledgement)]
    event = EdgeEvent.from_acknowledgement(acknowledgement)
    assert store.enqueue(event, transport.publications[0], NOW) is EnqueueResult.BROKER_ACCEPTED

    ingestion, persistence = _cloud_ingestion()
    ingested = ingestion.process(
        transport.publications[0].topic,
        transport.publications[0].payload.encode(),
        qos=1,
        retain=False,
    )
    assert ingested.outcome is IngestionOutcome.INSERTED
    assert len(persistence.acknowledgements) == 1
    _apply_cloud_receipt(ingested, store, topics)
    assert store.enqueue(event, transport.publications[0], NOW) is EnqueueResult.CLOUD_CONFIRMED


def test_stale_ai_snapshot_is_blocked_before_pump_or_lifecycle(tmp_path: Path) -> None:
    topics = TopicBuilder(FARM_ID, DEVICE_ID)
    transport = FakeMqttTransport()
    transport.connect()
    store, outbox = _outbox(tmp_path, transport)
    publisher = MqttAcknowledgementPublisher(transport, topics, durable_publisher=outbox)
    pump = FakePump()
    controller = SafePumpController(pump, FakeScheduler())
    handler = PumpCommandHandler(
        controller,
        PumpSafetyConfig(FARM_ID, DEVICE_ID, 120),
        clock=lambda: NOW,
        lifecycle_sink=publisher.publish,
    )
    config = AutomaticIrrigationConfig(True, duration_seconds=10, cooldown_seconds=60)
    clock = FixedClock()
    app = AutomaticIrrigationService(
        FixedSnapshots(_snapshot(stale=True)),
        IrrigationInferenceService(
            PortableTreeModelAdapter(), InferenceConfig(max_age_seconds=30), clock=lambda: NOW
        ),
        IndependentAutomaticSafetyGate(
            config, InferenceConfig(max_age_seconds=30), controller, clock
        ),
        handler,
        config,
        clock,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        command_id_factory=lambda: COMMAND_ID,
    )

    result = app.evaluate_once()

    assert result.safety_decision.reason_code is AutomaticSafetyReason.SENSOR_STALE
    assert result.command_submitted is False
    assert pump.active is False
    assert pump.calls == []
    assert transport.publications == []
    assert store.pending(limit=10) == ()


def test_manual_mqtt_command_reaches_fake_pump_and_durable_correlated_ack(
    tmp_path: Path,
) -> None:
    topics = TopicBuilder(FARM_ID, DEVICE_ID)
    transport = FakeMqttTransport()
    transport.connect()
    store, outbox = _outbox(tmp_path, transport)
    publisher = MqttAcknowledgementPublisher(transport, topics, durable_publisher=outbox)
    pump = FakePump()
    handler = PumpCommandHandler(
        SafePumpController(pump, FakeScheduler()),
        PumpSafetyConfig(FARM_ID, DEVICE_ID, 120),
        clock=lambda: NOW,
        acknowledgement_id_factory=lambda: ACK_ID,
        acknowledgement_sink=publisher.publish,
    )
    processor = MqttPumpCommandProcessor(handler, publisher, topics, clock=lambda: NOW)
    command = PumpCommand(
        command_id=COMMAND_ID,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        action=PumpAction.ON,
        issued_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        requested_by=REQUESTER_ID,
        duration_seconds=10,
    )

    processor.process(
        ReceivedMqttMessage(topics.pump_command(), command.to_json().encode(), 1, False)
    )

    assert pump.active is True
    assert len(transport.publications) == 1
    publication = transport.publications[0]
    acknowledgement = CommandAcknowledgement.from_json(publication.payload)
    assert acknowledgement.command_id == COMMAND_ID
    assert acknowledgement.acknowledgement_id == ACK_ID
    assert acknowledgement.status is AcknowledgementStatus.ACCEPTED
    assert publication.topic == topics.acknowledgement(COMMAND_ID)
    assert publication.qos == 1
    assert publication.retain is False
    assert (
        store.enqueue(EdgeEvent.from_acknowledgement(acknowledgement), publication, NOW)
        is EnqueueResult.BROKER_ACCEPTED
    )


def test_offline_ack_replay_preserves_identity_and_requires_cloud_receipt(
    tmp_path: Path,
) -> None:
    topics = TopicBuilder(FARM_ID, DEVICE_ID)
    transport = FakeMqttTransport(auto_connect=False)
    store, outbox = _outbox(tmp_path, transport)
    acknowledgement = CommandAcknowledgement(
        acknowledgement_id=ACK_ID,
        command_id=COMMAND_ID,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        status=AcknowledgementStatus.ACCEPTED,
        occurred_at=NOW,
        pump_state=True,
    )
    event = EdgeEvent.from_acknowledgement(acknowledgement)
    publication = _publication(topics, acknowledgement)

    assert outbox.submit(event, publication, attempt_now=True) is False
    pending = store.pending(limit=10)
    assert len(pending) == 1
    assert pending[0].event.event_id == ACK_ID
    assert pending[0].publication.payload == publication.payload

    transport.simulate_reconnect()
    outbox.drain()

    assert transport.publications == [publication]
    assert store.enqueue(event, publication, NOW) is EnqueueResult.BROKER_ACCEPTED
    assert len(store.pending(limit=10)) == 1

    ingestion, persistence = _cloud_ingestion()
    inserted = ingestion.process(
        publication.topic, publication.payload.encode(), qos=1, retain=False
    )
    duplicate = ingestion.process(
        publication.topic, publication.payload.encode(), qos=1, retain=False
    )
    assert inserted.outcome is IngestionOutcome.INSERTED
    assert duplicate.outcome is IngestionOutcome.DUPLICATE
    assert len(persistence.acknowledgements) == 1
    assert len(store.pending(limit=10)) == 1

    _apply_cloud_receipt(duplicate, store, topics)
    assert store.pending(limit=10) == ()
    assert store.enqueue(event, publication, NOW) is EnqueueResult.CLOUD_CONFIRMED
