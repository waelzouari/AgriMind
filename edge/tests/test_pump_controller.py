from __future__ import annotations

import pytest

from agrimind_edge.adapters.fake import FakePump, FakeScheduler
from agrimind_edge.application.pump_controller import PumpOperationFailed, SafePumpController
from agrimind_edge.domain import PumpState


def test_shutdown_cancels_timer_forces_off_and_cleans_up() -> None:
    pump = FakePump()
    scheduler = FakeScheduler()
    controller = SafePumpController(pump, scheduler)
    controller.start(10, lambda result: pytest.fail(f"unexpected callback: {result}"))

    controller.shutdown()

    assert controller.state is PumpState.OFF
    assert pump.active is False
    assert pump.initialized is False
    assert scheduler.calls[0].cancelled is True
    assert pump.calls[-2:] == ["turn_off", "cleanup"]


def test_shutdown_failure_enters_fault() -> None:
    pump = FakePump({"turn_off": [RuntimeError("off")], "cleanup": [RuntimeError("cleanup")]})
    controller = SafePumpController(pump, FakeScheduler())

    with pytest.raises(PumpOperationFailed) as captured:
        controller.shutdown()

    assert captured.value.safe_off is False
    assert controller.state is PumpState.FAULT


def test_cancelled_old_timer_cannot_stop_a_later_cycle() -> None:
    pump = FakePump()
    scheduler = FakeScheduler()
    controller = SafePumpController(pump, scheduler)
    controller.start(10, lambda result: None)
    first_timer = scheduler.calls[0]
    controller.stop()
    controller.start(20, lambda result: None)

    first_timer.callback()

    assert controller.state is PumpState.RUNNING
    assert pump.active is True
    assert pump.calls.count("turn_off") == 1
