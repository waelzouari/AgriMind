import 'dart:async';
import 'dart:convert';

import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/dashboard/infrastructure/mqtt_telemetry_repository.dart';
import 'package:agrimind/features/dashboard/infrastructure/mqtt_wire_client.dart';
import 'package:flutter_test/flutter_test.dart';

const farmId = 'efe00b4d-01e6-4565-8d86-18ba27f76666';
const deviceId = '4b9b0c3e-e810-4225-93d8-fd69523a295e';

final class FakeWireClient implements MqttWireClient {
  final connections = StreamController<WireConnectionEvent>.broadcast();
  final inbound = StreamController<WireMessage>.broadcast();
  String? filter;
  int disconnects = 0;
  @override
  Stream<WireConnectionEvent> get connectionEvents => connections.stream;
  @override
  Stream<WireMessage> get messages => inbound.stream;
  @override
  Future<void> connect({required String topicFilter}) async =>
      filter = topicFilter;
  @override
  Future<void> disconnect() async => disconnects++;
}

Map<String, Object> payload({String farm = farmId}) => {
  'schema_version': 1,
  'message_id': '33333333-3333-4333-8333-333333333333',
  'farm_id': farm,
  'device_id': deviceId,
  'metric': 'temperature',
  'value': 26,
  'unit': '°C',
  'recorded_at': '2026-09-23T18:00:00Z',
  'quality': 'valid',
};

void main() {
  test(
    'subscribes only to telemetry and forwards reconnect and valid data',
    () async {
      final wire = FakeWireClient();
      final repository = MqttTelemetryRepository(wire);
      final events = <TelemetryEvent>[];
      final subscription = repository.events.listen(events.add);
      await repository.connect(farmId: farmId, deviceId: deviceId);
      expect(
        wire.filter,
        'agrimind/v1/farms/$farmId/devices/$deviceId/telemetry/+',
      );
      wire.connections.add(WireConnectionEvent.reconnecting);
      wire.inbound.add(
        WireMessage(
          topic:
              'agrimind/v1/farms/$farmId/devices/$deviceId/telemetry/temperature',
          payload: jsonEncode(payload()),
        ),
      );
      await pumpEventQueue();
      expect(
        events.whereType<TelemetryConnectionChanged>().last.phase,
        MqttConnectionPhase.reconnecting,
      );
      expect(events.whereType<TelemetryReceived>(), hasLength(1));
      await repository.disconnect();
      await subscription.cancel();
    },
  );

  test('drops malformed, wrong-identity and unauthorized topics', () async {
    final wire = FakeWireClient();
    final repository = MqttTelemetryRepository(wire);
    final events = <TelemetryEvent>[];
    final subscription = repository.events.listen(events.add);
    await repository.connect(farmId: farmId, deviceId: deviceId);
    wire.inbound
      ..add(const WireMessage(topic: 'bad/topic', payload: '{bad'))
      ..add(
        WireMessage(
          topic:
              'agrimind/v1/farms/$farmId/devices/$deviceId/telemetry/temperature',
          payload: jsonEncode(
            payload(farm: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
          ),
        ),
      )
      ..add(
        WireMessage(
          topic: 'agrimind/v1/farms/$farmId/devices/$deviceId/status/device',
          payload: jsonEncode(payload()),
        ),
      );
    await pumpEventQueue();
    expect(events.whereType<TelemetryReceived>(), isEmpty);
    await repository.disconnect();
    await subscription.cancel();
  });
}
