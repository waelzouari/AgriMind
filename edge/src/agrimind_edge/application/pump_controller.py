"""Serialized, fail-safe pump state machine using only the PumpPort boundary."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock

from agrimind_edge.application.ports import PumpPort, ScheduledCall, SchedulerPort
from agrimind_edge.domain.pump import AutomaticStopResult, PumpDecisionCode, PumpState


class PumpTransitionRejected(Exception):
    def __init__(self, code: PumpDecisionCode) -> None:
        super().__init__(code.value)
        self.code = code


class PumpOperationFailed(Exception):
    def __init__(self, code: PumpDecisionCode, *, safe_off: bool) -> None:
        super().__init__(code.value)
        self.code = code
        self.safe_off = safe_off


class SafePumpController:
    """Own explicit OFF/RUNNING/FAULT transitions and the bounded run timer."""

    def __init__(self, pump: PumpPort, scheduler: SchedulerPort) -> None:
        self._pump = pump
        self._scheduler = scheduler
        self._state = PumpState.OFF
        self._timer: ScheduledCall | None = None
        self._cycle = 0
        self._lock = RLock()

    @property
    def state(self) -> PumpState:
        with self._lock:
            return self._state

    def start(
        self,
        duration_seconds: int,
        on_automatic_stop: Callable[[AutomaticStopResult], None],
    ) -> None:
        with self._lock:
            if self._state is PumpState.RUNNING:
                raise PumpTransitionRejected(PumpDecisionCode.ALREADY_RUNNING)
            if self._state is PumpState.FAULT:
                raise PumpTransitionRejected(PumpDecisionCode.CONTROLLER_FAULT)
            if self._observed_active():
                safe_off = self._force_off_locked()
                raise PumpOperationFailed(
                    PumpDecisionCode.STATE_INCONSISTENT,
                    safe_off=safe_off,
                )

            try:
                result = self._pump.turn_on()
                if result["pump"] is not True or not self._observed_active():
                    raise RuntimeError("pump did not report an active state")
            except Exception:
                safe_off = self._force_off_locked()
                raise PumpOperationFailed(
                    PumpDecisionCode.PUMP_ACTUATION_FAILED,
                    safe_off=safe_off,
                ) from None

            self._state = PumpState.RUNNING
            self._cycle += 1
            cycle = self._cycle

            def automatic_stop() -> None:
                result = self._automatic_stop(cycle)
                if result is not None:
                    on_automatic_stop(result)

            try:
                self._timer = self._scheduler.schedule(duration_seconds, automatic_stop)
            except Exception:
                safe_off = self._force_off_locked()
                raise PumpOperationFailed(
                    PumpDecisionCode.SCHEDULER_FAILED,
                    safe_off=safe_off,
                ) from None

    def stop(self) -> None:
        with self._lock:
            self._cancel_timer_locked()
            if self._state is PumpState.OFF:
                try:
                    if not self._observed_active():
                        return
                except Exception:
                    pass
            if self._turn_off_locked():
                return
            safe_off = self._force_off_locked()
            raise PumpOperationFailed(
                PumpDecisionCode.PUMP_ACTUATION_FAILED,
                safe_off=safe_off,
            )

    def force_safe_off(self) -> bool:
        with self._lock:
            self._cancel_timer_locked()
            return self._force_off_locked()

    def shutdown(self) -> None:
        with self._lock:
            self._cancel_timer_locked()
            safe_off = self._force_off_locked()
            try:
                self._pump.cleanup()
            except Exception:
                self._state = PumpState.FAULT
                raise PumpOperationFailed(
                    PumpDecisionCode.PUMP_ACTUATION_FAILED,
                    safe_off=False,
                ) from None
            if not safe_off:
                raise PumpOperationFailed(
                    PumpDecisionCode.PUMP_ACTUATION_FAILED,
                    safe_off=False,
                )
            self._state = PumpState.OFF

    def _automatic_stop(self, cycle: int) -> AutomaticStopResult | None:
        with self._lock:
            if cycle != self._cycle or self._state is not PumpState.RUNNING:
                return None
            self._timer = None
            if self._turn_off_locked():
                return AutomaticStopResult(PumpState.OFF)
            safe_off = self._force_off_locked()
            return AutomaticStopResult(
                PumpState.OFF if safe_off else PumpState.FAULT,
                PumpDecisionCode.PUMP_ACTUATION_FAILED,
            )

    def _turn_off_locked(self) -> bool:
        try:
            result = self._pump.turn_off()
            if result["pump"] is not False or self._observed_active():
                raise RuntimeError("pump did not report an inactive state")
        except Exception:
            return False
        self._state = PumpState.OFF
        return True

    def _force_off_locked(self) -> bool:
        if self._turn_off_locked():
            return True
        self._state = PumpState.FAULT
        return False

    def _observed_active(self) -> bool:
        return self._pump.get_state()

    def _cancel_timer_locked(self) -> None:
        self._cycle += 1
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
