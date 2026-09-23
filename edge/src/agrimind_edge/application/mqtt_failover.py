"""Single-active-broker MQTT failover and cloud-outbox routing."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import suppress
from threading import RLock

from agrimind_edge.application.mqtt_ports import (
    ConnectionHandler,
    DisconnectionHandler,
    MessageHandler,
    MqttPublishReceipt,
    MqttTransport,
)
from agrimind_edge.application.persistence_ports import DurableEventPublisher
from agrimind_edge.domain.broker import BrokerState, FailoverPolicy
from agrimind_edge.domain.mqtt import MqttPublication
from agrimind_edge.domain.persistence import EdgeEvent


class FailoverMqttTransport:
    """Expose one active MQTT transport while probing Cloud without subscribing."""

    def __init__(
        self,
        cloud: MqttTransport,
        local: MqttTransport,
        policy: FailoverPolicy,
        *,
        monotonic: Callable[[], float],
        logger: logging.Logger | None = None,
    ) -> None:
        self._cloud = cloud
        self._local = local
        self._policy = policy
        self._monotonic = monotonic
        self._logger = logger or logging.getLogger(__name__)
        self._state = BrokerState.OFFLINE
        self._failures = 0
        self._state_since = monotonic()
        self._local_since: float | None = None
        self._cloud_connected = False
        self._local_connected = False
        self._switching = False
        self._will: MqttPublication | None = None
        self._subscriptions: dict[str, tuple[int, MessageHandler]] = {}
        self._on_connected: ConnectionHandler = lambda: None
        self._on_disconnected: DisconnectionHandler = lambda: None
        self._lock = RLock()
        cloud.set_connection_handlers(self._cloud_up, self._cloud_down)
        local.set_connection_handlers(self._local_up, self._local_down)

    @property
    def state(self) -> BrokerState:
        with self._lock:
            return self._state

    @property
    def cloud_active(self) -> bool:
        return self.state is BrokerState.CLOUD_ACTIVE

    @property
    def local_active(self) -> bool:
        return self.state in {BrokerState.LOCAL_FALLBACK, BrokerState.CLOUD_RECOVERY}

    def set_connection_handlers(
        self, on_connected: ConnectionHandler, on_disconnected: DisconnectionHandler
    ) -> None:
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected

    def configure_last_will(self, publication: MqttPublication) -> None:
        self._will = publication
        self._cloud.configure_last_will(publication)
        self._local.configure_last_will(publication)

    def connect(self) -> None:
        if self._will is None:
            raise RuntimeError("MQTT last will must be configured before connect")
        try:
            self._cloud.connect()
        except Exception:
            with self._lock:
                self._failures += 1
                self._set_state(
                    BrokerState.FAILOVER_PENDING if self._policy.enabled else BrokerState.OFFLINE
                )
            self._on_disconnected()

    def publish(self, publication: MqttPublication) -> MqttPublishReceipt:
        with self._lock:
            if self.cloud_active:
                return self._cloud.publish(publication)
            if self.local_active:
                return self._local.publish(publication)
        raise RuntimeError("no active MQTT broker")

    def subscribe(self, topic: str, qos: int, handler: MessageHandler) -> None:
        with self._lock:
            self._subscriptions[topic] = (qos, handler)
            self._active_transport().subscribe(topic, qos, handler)

    def disconnect(self) -> None:
        with self._lock:
            self._switching = True
            try:
                self._cloud.disconnect()
                self._local.disconnect()
            finally:
                self._switching = False
                self._set_state(BrokerState.OFFLINE)

    def evaluate(self) -> None:
        """Advance time-based transitions; call from the owning runtime tick."""
        with self._lock:
            elapsed = self._monotonic() - self._state_since
            if self._state is BrokerState.FAILOVER_PENDING:
                if (
                    self._failures >= self._policy.cloud_failure_threshold
                    and elapsed >= self._policy.failover_delay_seconds
                ):
                    try:
                        self._local.connect()
                    except Exception:
                        self._set_state(BrokerState.OFFLINE)
            elif (
                self._state is BrokerState.LOCAL_FALLBACK
                and elapsed >= self._policy.cloud_probe_interval_seconds
            ):
                # Paho's bounded reconnect loop is the Cloud probe. Advancing
                # this timestamp makes the cadence observable and testable.
                self._state_since = self._monotonic()
            elif (
                self._state is BrokerState.CLOUD_RECOVERY
                and elapsed >= self._policy.cloud_stability_seconds
            ):
                local_elapsed = (
                    self._monotonic() - self._local_since if self._local_since is not None else 0
                )
                if local_elapsed >= self._policy.local_min_active_seconds:
                    self._promote_cloud()
            elif (
                self._state is BrokerState.OFFLINE
                and self._policy.enabled
                and elapsed >= self._policy.cloud_probe_interval_seconds
            ):
                try:
                    if self._failures >= self._policy.cloud_failure_threshold:
                        self._local.connect()
                    else:
                        self._cloud.connect()
                except Exception:
                    self._failures += 1
                    self._state_since = self._monotonic()

    def _cloud_up(self) -> None:
        with self._lock:
            self._cloud_connected = True
            if self.local_active:
                self._set_state(BrokerState.CLOUD_RECOVERY)
                return
            self._failures = 0
            self._set_state(BrokerState.CLOUD_ACTIVE)
            self._on_connected()

    def _cloud_down(self) -> None:
        with self._lock:
            self._cloud_connected = False
            if self._switching:
                return
            if self.local_active:
                self._set_state(BrokerState.LOCAL_FALLBACK)
                return
            self._failures += 1
            self._on_disconnected()
            if self._policy.enabled:
                self._set_state(BrokerState.FAILOVER_PENDING)
            else:
                self._set_state(BrokerState.OFFLINE)

    def _local_up(self) -> None:
        with self._lock:
            self._local_connected = True
            if self._state is BrokerState.CLOUD_ACTIVE:
                self._switching = True
                try:
                    self._local.disconnect()
                finally:
                    self._switching = False
                self._local_connected = False
                return
            self._local_since = self._monotonic()
            self._set_state(BrokerState.LOCAL_FALLBACK)
            self._on_connected()

    def _local_down(self) -> None:
        with self._lock:
            self._local_connected = False
            self._local_since = None
            if self._switching:
                return
            self._on_disconnected()
            if self._cloud_connected:
                self._set_state(BrokerState.CLOUD_ACTIVE)
                self._on_connected()
            else:
                self._set_state(BrokerState.OFFLINE)

    def _promote_cloud(self) -> None:
        if not self._cloud_connected:
            self._set_state(BrokerState.LOCAL_FALLBACK)
            return
        self._switching = True
        try:
            if self._will is not None:
                with suppress(Exception):
                    self._local.publish(self._will).wait_for_confirmation(10.0)
            self._local.disconnect()
        finally:
            self._switching = False
        self._local_connected = False
        self._local_since = None
        self._set_state(BrokerState.CLOUD_ACTIVE)
        self._on_disconnected()
        self._on_connected()

    def _active_transport(self) -> MqttTransport:
        if self.cloud_active:
            return self._cloud
        if self.local_active:
            return self._local
        raise RuntimeError("no active MQTT broker")

    def _set_state(self, state: BrokerState) -> None:
        if state is self._state:
            return
        previous = self._state
        self._state = state
        self._state_since = self._monotonic()
        self._logger.info(
            "mqtt_broker_state_changed",
            extra={
                "event": "mqtt_broker_state_changed",
                "previous_state": previous.value,
                "state": state.value,
            },
        )


class FailoverEventPublisher:
    """Keep Cloud durability authoritative while mirroring during local fallback."""

    def __init__(
        self,
        cloud_outbox: DurableEventPublisher,
        local: MqttTransport,
        selector: FailoverMqttTransport,
        *,
        confirmation_timeout_seconds: float = 10.0,
    ) -> None:
        self._cloud_outbox = cloud_outbox
        self._local = local
        self._selector = selector
        self._confirmation_timeout_seconds = confirmation_timeout_seconds

    def initialize(self) -> bool:
        return self._cloud_outbox.initialize()

    def submit(
        self,
        event: EdgeEvent,
        publication: MqttPublication,
        *,
        attempt_now: bool,
        replay_delivered: bool = False,
    ) -> bool:
        cloud_result = self._cloud_outbox.submit(
            event,
            publication,
            attempt_now=attempt_now and self._selector.cloud_active,
            replay_delivered=replay_delivered,
        )
        if not self._selector.local_active:
            return cloud_result
        try:
            receipt = self._local.publish(publication)
            return receipt.wait_for_confirmation(self._confirmation_timeout_seconds)
        except Exception:
            return False

    def request_drain(self) -> None:
        if self._selector.cloud_active:
            self._cloud_outbox.request_drain()
