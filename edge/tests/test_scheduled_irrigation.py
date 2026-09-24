from __future__ import annotations

import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from uuid import UUID

import pytest

from agrimind_edge.adapters.fake import FakePump, FakeScheduler
from agrimind_edge.adapters.persistence import SqliteEventOutboxStore
from agrimind_edge.adapters.persistence.migrations import MIGRATIONS
from agrimind_edge.application.persistence_ports import PersistenceConflict, PersistenceError
from agrimind_edge.application.pump_command_handler import PumpCommandHandler
from agrimind_edge.application.pump_controller import SafePumpController
from agrimind_edge.application.scheduled_irrigation import (
    DuplicateScheduleError,
    PumpCommandBoundary,
    ScheduledIrrigationRunner,
    ScheduledIrrigationService,
    ScheduleTooOldError,
)
from agrimind_edge.config import PumpSafetyConfig
from agrimind_edge.contracts import CommandAcknowledgement, PumpCommand
from agrimind_edge.contracts.enums import AcknowledgementStatus
from agrimind_edge.domain.schedules import (
    IrrigationSchedule,
    OccurrenceStatus,
    command_id_for,
    occurrence_id_for,
    scheduler_requested_by,
)

NOW = datetime(2026, 9, 25, 7, 30, tzinfo=UTC)
FARM_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
SCHEDULE_ID = UUID("33333333-3333-4333-8333-333333333333")


class FakeClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def now_utc(self) -> datetime:
        return self.now


def open_store(path: Path) -> SqliteEventOutboxStore:
    store = SqliteEventOutboxStore(path)
    store.initialize()
    return store


def schedule(
    schedule_id: UUID = SCHEDULE_ID,
    *,
    scheduled_for: datetime = NOW,
    duration: int = 30,
) -> IrrigationSchedule:
    return IrrigationSchedule(
        schedule_id,
        FARM_ID,
        DEVICE_ID,
        scheduled_for,
        duration,
        True,
        NOW - timedelta(minutes=1),
        NOW - timedelta(minutes=1),
    )


def service(
    store: SqliteEventOutboxStore,
    clock: FakeClock,
    handler: PumpCommandBoundary | None = None,
    *,
    lateness: int = 30,
) -> ScheduledIrrigationService:
    return ScheduledIrrigationService(
        store,
        handler,
        clock,
        farm_id=FARM_ID,
        device_id=DEVICE_ID,
        max_lateness_seconds=lateness,
    )


@pytest.mark.parametrize("duration", [1, 600])
def test_create_accepts_contract_duration_boundaries(tmp_path: Path, duration: int) -> None:
    store = open_store(tmp_path / "edge.sqlite3")
    created = service(store, FakeClock()).create_schedule(
        NOW + timedelta(hours=1), duration, schedule_id=SCHEDULE_ID
    )

    assert created.duration_seconds == duration
    assert store.list_schedules()[0].schedule == created


@pytest.mark.parametrize("duration", [0, 601])
def test_create_rejects_invalid_duration(tmp_path: Path, duration: int) -> None:
    store = open_store(tmp_path / "edge.sqlite3")

    with pytest.raises(ValueError, match="duration_seconds"):
        service(store, FakeClock()).create_schedule(NOW, duration)


def test_create_rejects_naive_old_and_duplicate_schedule(tmp_path: Path) -> None:
    store = open_store(tmp_path / "edge.sqlite3")
    schedules = service(store, FakeClock())

    with pytest.raises(ValueError, match="UTC"):
        schedules.create_schedule(NOW.replace(tzinfo=None), 10)
    with pytest.raises(ScheduleTooOldError, match="schedule_too_old"):
        schedules.create_schedule(NOW - timedelta(seconds=31), 10)

    schedules.create_schedule(NOW - timedelta(seconds=30), 10, schedule_id=SCHEDULE_ID)
    with pytest.raises(DuplicateScheduleError, match="duplicate_schedule"):
        schedules.create_schedule(NOW, 10, schedule_id=SCHEDULE_ID)


def test_identity_is_canonical_and_deterministic() -> None:
    instant = datetime(2026, 9, 25, 9, 30, tzinfo=UTC)
    equivalent = datetime.fromisoformat("2026-09-25T11:30:00+02:00").astimezone(UTC)
    first = occurrence_id_for(SCHEDULE_ID, instant)

    assert occurrence_id_for(SCHEDULE_ID, equivalent) == first
    assert occurrence_id_for(UUID(int=SCHEDULE_ID.int + 1), instant) != first
    assert occurrence_id_for(SCHEDULE_ID, instant + timedelta(seconds=1)) != first
    assert command_id_for(first) == command_id_for(first)
    assert scheduler_requested_by(FARM_ID, DEVICE_ID) == scheduler_requested_by(FARM_ID, DEVICE_ID)


def test_disable_is_soft_and_history_survives(tmp_path: Path) -> None:
    store = open_store(tmp_path / "edge.sqlite3")
    store.create_schedule(schedule())
    occurrence = store.claim_due(NOW, timedelta(seconds=30))[0]
    store.mark_occurrence(
        occurrence.occurrence_id,
        OccurrenceStatus.COMMAND_ACCEPTED,
        NOW,
        ack_status="accepted",
    )

    assert store.disable_schedule(SCHEDULE_ID, NOW) is True
    summary = store.list_schedules()[0]
    assert summary.schedule.enabled is False
    assert summary.occurrence_status is OccurrenceStatus.COMMAND_ACCEPTED


def test_due_boundaries_and_missed_policy(tmp_path: Path) -> None:
    cases = [
        (-1, None),
        (0, OccurrenceStatus.CLAIMED),
        (29, OccurrenceStatus.CLAIMED),
        (30, OccurrenceStatus.CLAIMED),
        (31, OccurrenceStatus.MISSED),
    ]
    for index, (seconds, expected) in enumerate(cases):
        store = open_store(tmp_path / f"edge-{index}.sqlite3")
        store.create_schedule(schedule(scheduled_for=NOW))
        claimed = store.claim_due(NOW + timedelta(seconds=seconds), timedelta(seconds=30))
        assert (claimed[0].status if claimed else None) is expected


def test_due_order_disable_and_duplicate_tick(tmp_path: Path) -> None:
    store = open_store(tmp_path / "edge.sqlite3")
    later_id = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
    first_id = UUID("00000000-0000-4000-8000-000000000001")
    disabled_id = UUID("00000000-0000-4000-8000-000000000002")
    store.create_schedule(schedule(later_id, scheduled_for=NOW + timedelta(seconds=1)))
    store.create_schedule(schedule(first_id))
    store.create_schedule(schedule(disabled_id))
    store.disable_schedule(disabled_id, NOW)

    claimed = store.claim_due(NOW + timedelta(seconds=1), timedelta(seconds=30))
    assert [item.schedule_id for item in claimed] == [first_id, later_id]
    assert store.claim_due(NOW + timedelta(seconds=1), timedelta(seconds=30)) == ()


def test_schedule_survives_reopen_and_current_schema_migrates(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    for version, migration in enumerate(MIGRATIONS[:2], start=1):
        connection.executescript(migration)
        connection.execute(
            "INSERT INTO schema_migrations VALUES (?, '2026-09-25T00:00:00.000Z')", (version,)
        )
    connection.execute(
        """
        INSERT INTO processed_commands(
            command_id, command_fingerprint, acknowledgement_payload,
            processed_at, expires_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            "44444444-4444-4444-8444-444444444444",
            "existing-fingerprint",
            "{}",
            "2026-09-25T00:00:00.000Z",
            "2026-09-26T00:00:00.000Z",
        ),
    )
    connection.commit()
    connection.close()

    first = open_store(path)
    first.create_schedule(schedule())
    first.close()
    reopened = open_store(path)

    assert reopened.list_schedules()[0].schedule.schedule_id == SCHEDULE_ID
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT COUNT(*) FROM processed_commands").fetchone()[0] == 1
    assert connection.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall() == [
        (1,),
        (2,),
        (3,),
    ]
    connection.close()


def test_migration_is_idempotent_across_repeated_initialization(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    for _ in range(3):
        store = open_store(path)
        store.close()

    connection = sqlite3.connect(path)
    versions = connection.execute(
        "SELECT version, COUNT(*) FROM schema_migrations GROUP BY version ORDER BY version"
    ).fetchall()
    assert versions == [(1, 1), (2, 1), (3, 1)]
    connection.close()


def test_two_repositories_claim_occurrence_once(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    first = open_store(path)
    second = open_store(path)
    first.create_schedule(schedule())

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda store: store.claim_due(NOW, timedelta(seconds=30)),
                (first, second),
            )
        )

    assert sorted(len(result) for result in results) == [0, 1]


def test_concurrent_disable_and_claim_converge_safely(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    claimant = open_store(path)
    administrator = open_store(path)
    claimant.create_schedule(schedule())

    with ThreadPoolExecutor(max_workers=2) as executor:
        claim_future = executor.submit(claimant.claim_due, NOW, timedelta(seconds=30))
        disable_future = executor.submit(administrator.disable_schedule, SCHEDULE_ID, NOW)
        claimed = claim_future.result()
        assert disable_future.result() is True

    summary = claimant.list_schedules()[0]
    assert summary.schedule.enabled is False
    assert len(claimed) in {0, 1}
    assert claimant.claim_due(NOW, timedelta(seconds=30)) == ()


def test_claim_rolls_back_occurrence_when_schedule_disable_fails(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    store = open_store(path)
    store.create_schedule(schedule())
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TRIGGER reject_schedule_disable
        BEFORE UPDATE ON irrigation_schedules
        BEGIN SELECT RAISE(ABORT, 'synthetic disable failure'); END
        """
    )
    connection.commit()
    connection.close()

    with pytest.raises(PersistenceError, match="schedule claim"):
        store.claim_due(NOW, timedelta(seconds=30))

    connection = sqlite3.connect(path)
    assert connection.execute("SELECT enabled FROM irrigation_schedules").fetchone() == (1,)
    assert connection.execute(
        "SELECT COUNT(*) FROM irrigation_schedule_occurrences"
    ).fetchone() == (0,)
    connection.close()


def test_locked_database_claim_fails_without_command_or_occurrence(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    creator = open_store(path)
    creator.create_schedule(schedule())
    creator.close()
    worker = SqliteEventOutboxStore(path, busy_timeout_ms=1)
    worker.initialize()
    locker = sqlite3.connect(path)
    locker.execute("BEGIN IMMEDIATE")

    try:
        with pytest.raises(PersistenceError, match="claim failed"):
            worker.claim_due(NOW, timedelta(seconds=30))
    finally:
        locker.rollback()
        locker.close()

    connection = sqlite3.connect(path)
    assert connection.execute(
        "SELECT COUNT(*) FROM irrigation_schedule_occurrences"
    ).fetchone() == (0,)
    connection.close()


def test_malformed_persisted_timestamp_fails_safe(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    store = open_store(path)
    store.create_schedule(schedule())
    store.close()
    connection = sqlite3.connect(path)
    connection.execute("UPDATE irrigation_schedules SET scheduled_for = '!invalid-timestamp'")
    connection.commit()
    connection.close()
    reopened = open_store(path)

    with pytest.raises(PersistenceError, match="data is invalid"):
        reopened.claim_due(NOW, timedelta(seconds=30))

    connection = sqlite3.connect(path)
    assert connection.execute("SELECT enabled FROM irrigation_schedules").fetchone() == (1,)
    assert connection.execute(
        "SELECT COUNT(*) FROM irrigation_schedule_occurrences"
    ).fetchone() == (0,)
    connection.close()


def test_corrupt_database_is_rejected_before_schedule_processing(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"not a SQLite database")
    store = SqliteEventOutboxStore(path)

    with pytest.raises(PersistenceError, match="initialization failed"):
        store.initialize()


def test_recovery_marks_claimed_unknown_without_reactivation(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    store = open_store(path)
    store.create_schedule(schedule())
    claimed = store.claim_due(NOW, timedelta(seconds=30))[0]
    store.close()

    reopened = open_store(path)
    assert reopened.recover_non_terminal(NOW + timedelta(seconds=1)) == 1
    recovered = reopened.get_occurrence(claimed.occurrence_id)
    assert recovered is not None
    assert recovered.status is OccurrenceStatus.UNKNOWN_AFTER_RESTART
    assert reopened.claim_due(NOW + timedelta(seconds=2), timedelta(seconds=30)) == ()


def test_real_safe_boundary_dispatches_once_and_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    store = open_store(path)
    clock = FakeClock(NOW - timedelta(seconds=1))
    pump = FakePump()
    timer = FakeScheduler()
    controller = SafePumpController(pump, timer)
    handler = PumpCommandHandler(
        controller,
        PumpSafetyConfig(FARM_ID, DEVICE_ID, 60),
        clock=clock.now_utc,
        processed_command_store=store,
    )
    schedules = service(store, clock, handler)
    schedules.create_schedule(NOW, 30, schedule_id=SCHEDULE_ID)

    assert schedules.process_due() == ()
    clock.now = NOW
    occurrence = schedules.process_due()[0]
    assert pump.active is True
    assert len(timer.calls) == 1
    persisted = store.get_occurrence(occurrence.occurrence_id)
    assert persisted is not None
    assert persisted.status is OccurrenceStatus.COMMAND_ACCEPTED
    assert schedules.process_due() == ()
    timer.fire_next()
    assert pump.active is False

    store.close()
    reopened = open_store(path)
    assert reopened.claim_due(NOW + timedelta(seconds=1), timedelta(seconds=30)) == ()


def test_disabling_accepted_schedule_does_not_stop_active_pump(tmp_path: Path) -> None:
    store = open_store(tmp_path / "edge.sqlite3")
    clock = FakeClock()
    pump = FakePump()
    timer = FakeScheduler()
    handler = PumpCommandHandler(
        SafePumpController(pump, timer),
        PumpSafetyConfig(FARM_ID, DEVICE_ID),
        clock=clock.now_utc,
        processed_command_store=store,
    )
    schedules = service(store, clock, handler)
    schedules.create_schedule(NOW, 10, schedule_id=SCHEDULE_ID)
    schedules.process_due()

    schedules.disable_schedule(SCHEDULE_ID)

    assert pump.active is True
    assert pump.calls.count("turn_off") == 0


def test_each_dispatch_uses_current_clock_for_command_ttl(tmp_path: Path) -> None:
    class AdvancingHandler:
        def __init__(self, clock: FakeClock) -> None:
            self.clock = clock
            self.commands: list[PumpCommand] = []

        def handle(self, command: PumpCommand) -> CommandAcknowledgement:
            self.commands.append(command)
            self.clock.now += timedelta(seconds=2)
            return CommandAcknowledgement(
                UUID(int=len(self.commands)),
                command.command_id,
                command.farm_id,
                command.device_id,
                AcknowledgementStatus.REJECTED,
                self.clock.now,
                reason_code="synthetic_rejection",
                pump_state=False,
            )

    store = open_store(tmp_path / "edge.sqlite3")
    first_id = UUID("00000000-0000-4000-8000-000000000001")
    second_id = UUID("00000000-0000-4000-8000-000000000002")
    store.create_schedule(schedule(first_id))
    store.create_schedule(schedule(second_id))
    clock = FakeClock()
    handler = AdvancingHandler(clock)

    service(store, clock, handler).process_due()

    assert [command.issued_at for command in handler.commands] == [
        NOW,
        NOW + timedelta(seconds=2),
    ]
    assert all(
        command.expires_at == command.issued_at + timedelta(seconds=30)
        for command in handler.commands
    )


def test_generated_pump_command_uses_deterministic_local_identity(tmp_path: Path) -> None:
    class CapturingHandler:
        def __init__(self) -> None:
            self.commands: list[PumpCommand] = []

        def handle(self, command: PumpCommand) -> CommandAcknowledgement:
            self.commands.append(command)
            return CommandAcknowledgement(
                UUID(int=9),
                command.command_id,
                command.farm_id,
                command.device_id,
                AcknowledgementStatus.ACCEPTED,
                NOW,
                pump_state=True,
            )

    store = open_store(tmp_path / "edge.sqlite3")
    store.create_schedule(schedule(duration=12))
    handler = CapturingHandler()

    occurrence = service(store, FakeClock(), handler).process_due()[0]
    command = handler.commands[0]

    assert command.command_id == command_id_for(occurrence.occurrence_id)
    assert command.farm_id == FARM_ID
    assert command.device_id == DEVICE_ID
    assert command.duration_seconds == 12
    assert command.issued_at == NOW
    assert command.expires_at == NOW + timedelta(seconds=30)
    assert command.requested_by == scheduler_requested_by(FARM_ID, DEVICE_ID)


def test_command_boundary_exception_is_persisted_as_safe_failure(tmp_path: Path) -> None:
    class FailingHandler:
        def handle(self, command: PumpCommand) -> CommandAcknowledgement:
            del command
            raise RuntimeError("synthetic secret-looking detail")

    store = open_store(tmp_path / "edge.sqlite3")
    store.create_schedule(schedule())
    occurrence = service(store, FakeClock(), FailingHandler()).process_due()[0]
    result = store.get_occurrence(occurrence.occurrence_id)

    assert result is not None
    assert result.status is OccurrenceStatus.FAILED
    assert result.reason_code == "command_handler_failed_before_acknowledgement"


def test_persisted_target_is_not_remapped_after_reprovisioning(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    store = open_store(path)
    store.create_schedule(schedule())
    store.close()

    reprovisioned_farm = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    reprovisioned_device = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    reopened = open_store(path)
    clock = FakeClock()
    pump = FakePump()
    handler = PumpCommandHandler(
        SafePumpController(pump, FakeScheduler()),
        PumpSafetyConfig(reprovisioned_farm, reprovisioned_device),
        clock=clock.now_utc,
        processed_command_store=reopened,
    )
    schedules = ScheduledIrrigationService(
        reopened,
        handler,
        clock,
        farm_id=reprovisioned_farm,
        device_id=reprovisioned_device,
        max_lateness_seconds=30,
    )

    occurrence = schedules.process_due()[0]
    persisted = reopened.get_occurrence(occurrence.occurrence_id)

    assert occurrence.farm_id == FARM_ID
    assert occurrence.device_id == DEVICE_ID
    assert pump.calls.count("turn_on") == 0
    assert persisted is not None
    assert persisted.status is OccurrenceStatus.REJECTED
    assert persisted.reason_code == "wrong_farm"


def test_accepted_action_then_scheduler_persistence_failure_is_uncertain_and_not_replayed(
    tmp_path: Path,
) -> None:
    class FailAcceptedUpdateOnce:
        def __init__(self, wrapped: SqliteEventOutboxStore) -> None:
            self.wrapped = wrapped
            self.failed = False

        def __getattr__(self, name: str) -> object:
            return getattr(self.wrapped, name)

        def mark_occurrence(
            self,
            occurrence_id: UUID,
            status: OccurrenceStatus,
            decided_at: datetime,
            *,
            reason_code: str | None = None,
            ack_status: str | None = None,
        ) -> None:
            if status is OccurrenceStatus.COMMAND_ACCEPTED and not self.failed:
                self.failed = True
                raise PersistenceError("synthetic scheduler write failure")
            self.wrapped.mark_occurrence(
                occurrence_id,
                status,
                decided_at,
                reason_code=reason_code,
                ack_status=ack_status,
            )

    store = open_store(tmp_path / "edge.sqlite3")
    store.create_schedule(schedule())
    clock = FakeClock()
    pump = FakePump()
    timer = FakeScheduler()
    handler = PumpCommandHandler(
        SafePumpController(pump, timer),
        PumpSafetyConfig(FARM_ID, DEVICE_ID),
        clock=clock.now_utc,
        processed_command_store=store,
    )
    failing_store = FailAcceptedUpdateOnce(store)
    schedules = service(failing_store, clock, handler)  # type: ignore[arg-type]

    occurrence = schedules.process_due()[0]
    persisted = store.get_occurrence(occurrence.occurrence_id)

    assert pump.active is True
    assert persisted is not None
    assert persisted.status is OccurrenceStatus.UNKNOWN_AFTER_ACCEPTANCE
    assert persisted.reason_code == "accepted_outcome_persistence_failed"
    assert schedules.process_due() == ()
    assert pump.calls.count("turn_on") == 1


def test_scheduler_application_has_no_gpio_or_hardware_adapter_dependency() -> None:
    source = (
        Path(__file__).parents[1]
        / "src"
        / "agrimind_edge"
        / "application"
        / "scheduled_irrigation.py"
    ).read_text(encoding="utf-8")

    assert "RPi.GPIO" not in source
    assert "adapters.hardware" not in source
    assert "PumpPort" not in source


def test_busy_and_local_duration_limit_are_terminal_rejections(tmp_path: Path) -> None:
    store = open_store(tmp_path / "edge.sqlite3")
    clock = FakeClock()
    pump = FakePump()
    timer = FakeScheduler()
    controller = SafePumpController(pump, timer)
    handler = PumpCommandHandler(
        controller,
        PumpSafetyConfig(FARM_ID, DEVICE_ID, 20),
        clock=clock.now_utc,
        processed_command_store=store,
    )
    controller.start(10, lambda _result: None)
    store.create_schedule(schedule(duration=10))

    occurrence = service(store, clock, handler).process_due()[0]
    result = store.get_occurrence(occurrence.occurrence_id)
    assert result is not None
    assert result.status is OccurrenceStatus.REJECTED
    assert result.reason_code == "already_running"

    timer.fire_next()
    second_id = UUID(int=SCHEDULE_ID.int + 1)
    store.create_schedule(schedule(second_id, duration=30))
    second = service(store, clock, handler).process_due()[0]
    limited = store.get_occurrence(second.occurrence_id)
    assert limited is not None
    assert limited.status is OccurrenceStatus.REJECTED
    assert limited.reason_code == "duration_exceeds_local_limit"


def test_simultaneous_schedules_are_serial_and_second_is_busy(tmp_path: Path) -> None:
    store = open_store(tmp_path / "edge.sqlite3")
    clock = FakeClock()
    pump = FakePump()
    timer = FakeScheduler()
    handler = PumpCommandHandler(
        SafePumpController(pump, timer),
        PumpSafetyConfig(FARM_ID, DEVICE_ID),
        clock=clock.now_utc,
        processed_command_store=store,
    )
    first_id = UUID("00000000-0000-4000-8000-000000000001")
    second_id = UUID("00000000-0000-4000-8000-000000000002")
    store.create_schedule(schedule(second_id))
    store.create_schedule(schedule(first_id))

    occurrences = service(store, clock, handler).process_due()

    assert [item.schedule_id for item in occurrences] == [first_id, second_id]
    states = [store.get_occurrence(item.occurrence_id) for item in occurrences]
    assert [item.status for item in states if item is not None] == [
        OccurrenceStatus.COMMAND_ACCEPTED,
        OccurrenceStatus.REJECTED,
    ]
    assert len(timer.calls) == 1


def test_first_rejected_schedule_does_not_stop_due_batch(tmp_path: Path) -> None:
    store = open_store(tmp_path / "edge.sqlite3")
    clock = FakeClock()
    pump = FakePump()
    timer = FakeScheduler()
    handler = PumpCommandHandler(
        SafePumpController(pump, timer),
        PumpSafetyConfig(FARM_ID, DEVICE_ID, max_duration_seconds=20),
        clock=clock.now_utc,
        processed_command_store=store,
    )
    rejected_id = UUID("00000000-0000-4000-8000-000000000001")
    accepted_id = UUID("00000000-0000-4000-8000-000000000002")
    store.create_schedule(schedule(rejected_id, duration=30))
    store.create_schedule(schedule(accepted_id, duration=10))

    occurrences = service(store, clock, handler).process_due()
    states = [store.get_occurrence(item.occurrence_id) for item in occurrences]

    assert [item.status for item in states if item is not None] == [
        OccurrenceStatus.REJECTED,
        OccurrenceStatus.COMMAND_ACCEPTED,
    ]
    assert pump.calls.count("turn_on") == 1


def test_missed_after_downtime_and_clock_backward_never_dispatch(tmp_path: Path) -> None:
    path = tmp_path / "edge.sqlite3"
    store = open_store(path)
    clock = FakeClock(NOW - timedelta(minutes=1))
    pump = FakePump()
    timer = FakeScheduler()
    handler = PumpCommandHandler(
        SafePumpController(pump, timer),
        PumpSafetyConfig(FARM_ID, DEVICE_ID),
        clock=clock.now_utc,
        processed_command_store=store,
    )
    schedules = service(store, clock, handler)
    schedules.create_schedule(NOW, 10, schedule_id=SCHEDULE_ID)
    store.close()

    store = open_store(path)
    clock.now = NOW + timedelta(seconds=31)
    schedules = service(store, clock, handler)
    occurrence = schedules.process_due()[0]
    assert occurrence.status is OccurrenceStatus.MISSED
    assert pump.calls.count("turn_on") == 0

    clock.now = NOW - timedelta(seconds=1)
    assert schedules.process_due() == ()
    clock.now = NOW + timedelta(seconds=1)
    assert schedules.process_due() == ()
    assert pump.calls.count("turn_on") == 0


def test_runner_disabled_tick_and_stop_event() -> None:
    class StubService:
        calls = 0

        def process_due(self) -> tuple[()]:
            self.calls += 1
            return ()

    stub = StubService()
    assert (
        ScheduledIrrigationRunner(  # type: ignore[arg-type]
            stub, enabled=False, poll_interval_seconds=1
        ).tick()
        == ()
    )
    assert stub.calls == 0

    stop = Event()
    stop.set()
    ScheduledIrrigationRunner(  # type: ignore[arg-type]
        stub, enabled=True, poll_interval_seconds=0.5
    ).run(stop)
    assert stub.calls == 0


def test_runner_surfaces_fatal_storage_error_with_structured_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingService:
        def process_due(self) -> tuple[()]:
            raise PersistenceError("database unavailable")

    runner = ScheduledIrrigationRunner(  # type: ignore[arg-type]
        FailingService(), enabled=True, poll_interval_seconds=0.5
    )

    with caplog.at_level(logging.ERROR), pytest.raises(PersistenceError):
        runner.run(Event())

    assert any(record.event == "scheduler_fatal" for record in caplog.records)


def test_terminal_occurrence_cannot_be_overwritten(tmp_path: Path) -> None:
    store = open_store(tmp_path / "edge.sqlite3")
    store.create_schedule(schedule())
    occurrence = store.claim_due(NOW, timedelta(seconds=30))[0]
    store.mark_occurrence(occurrence.occurrence_id, OccurrenceStatus.FAILED, NOW)

    with pytest.raises(PersistenceConflict):
        store.mark_occurrence(
            occurrence.occurrence_id,
            OccurrenceStatus.COMMAND_ACCEPTED,
            NOW,
        )


def test_schedule_record_rejects_inconsistent_disabled_state() -> None:
    with pytest.raises(ValueError, match="enabled schedule"):
        replace(schedule(), disabled_at=NOW)
