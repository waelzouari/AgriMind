import 'dart:async';

import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/dashboard/domain/telemetry_reading.dart';
import 'package:agrimind/features/dashboard/infrastructure/mqtt_wire_client.dart';
import 'package:agrimind/features/dashboard/infrastructure/telemetry_topic.dart';

final class MqttTelemetryRepository implements TelemetryRepository {
  MqttTelemetryRepository(this._wireClient);
  final MqttWireClient _wireClient;
  final _events = StreamController<TelemetryEvent>.broadcast();
  StreamSubscription<WireConnectionEvent>? _connections;
  StreamSubscription<WireMessage>? _messages;

  @override
  Stream<TelemetryEvent> get events => _events.stream;

  @override
  Future<void> connect({
    required String farmId,
    required String deviceId,
  }) async {
    await disconnect();
    final topic = TelemetryTopic(farmId: farmId, deviceId: deviceId);
    _events.add(
      const TelemetryConnectionChanged(MqttConnectionPhase.connecting),
    );
    _connections = _wireClient.connectionEvents.listen((event) {
      final phase = switch (event) {
        WireConnectionEvent.connected => MqttConnectionPhase.connected,
        WireConnectionEvent.reconnecting => MqttConnectionPhase.reconnecting,
        WireConnectionEvent.disconnected => MqttConnectionPhase.disconnected,
        WireConnectionEvent.failure => MqttConnectionPhase.failure,
      };
      _events.add(TelemetryConnectionChanged(phase));
    });
    _messages = _wireClient.messages.listen((message) {
      final metric = topic.parse(message.topic);
      if (metric == null) return;
      final reading = TelemetryReading.tryDecode(
        message.payload,
        expectedFarmId: farmId,
        expectedDeviceId: deviceId,
        topicMetric: metric,
      );
      if (reading != null) _events.add(TelemetryReceived(reading));
    });
    await _wireClient.connect(topicFilter: topic.filter);
  }

  @override
  Future<void> disconnect() async {
    await _connections?.cancel();
    await _messages?.cancel();
    _connections = null;
    _messages = null;
    await _wireClient.disconnect();
  }
}
