import 'dart:async';
import 'dart:convert';

import 'package:agrimind/features/dashboard/infrastructure/mqtt_wire_client.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_repository.dart';
import 'package:agrimind/features/irrigation/domain/pump_command.dart';
import 'package:agrimind/features/irrigation/infrastructure/mqtt_command_wire_client.dart';
import 'package:agrimind/features/irrigation/infrastructure/mqtt_manual_irrigation_repository.dart';
import 'package:flutter_test/flutter_test.dart';

const farmId = '22222222-2222-4222-8222-222222222222';
const deviceId = '33333333-3333-4333-8333-333333333333';
const commandId = '11111111-1111-4111-8111-111111111111';

final class FakeCommandWire implements MqttCommandWireClient {
  final connections = StreamController<WireConnectionEvent>.broadcast();
  String? topic;
  String? payload;
  int publishes = 0;
  bool confirmation = true;
  @override
  Stream<WireConnectionEvent> get connectionEvents => connections.stream;
  @override
  Future<void> connect() async {}
  @override
  Future<void> disconnect() async {}
  @override
  Future<bool> publish({required String topic, required String payload}) async {
    publishes++;
    this.topic = topic;
    this.payload = payload;
    return confirmation;
  }
}

final class FakeAckWire implements MqttWireClient {
  final connections = StreamController<WireConnectionEvent>.broadcast();
  final inbound = StreamController<WireMessage>.broadcast();
  String? filter;
  @override
  Stream<WireConnectionEvent> get connectionEvents => connections.stream;
  @override
  Stream<WireMessage> get messages => inbound.stream;
  @override
  Future<void> connect({required String topicFilter}) async =>
      filter = topicFilter;
  @override
  Future<void> disconnect() async {}
}

PumpCommand command({String farm = farmId}) => PumpCommand(
  commandId: commandId,
  farmId: farm,
  deviceId: deviceId,
  durationSeconds: 60,
  issuedAt: DateTime.parse('2026-09-24T08:00:00Z'),
  expiresAt: DateTime.parse('2026-09-24T08:00:15Z'),
  requestedBy: '44444444-4444-4444-8444-444444444444',
);

void main() {
  test('uses only canonical command and acknowledgement topics', () async {
    final publisher = FakeCommandWire();
    final acknowledgements = FakeAckWire();
    final repository = MqttManualIrrigationRepository(
      commandClient: publisher,
      acknowledgementClient: acknowledgements,
    );
    await repository.connect(farmId: farmId, deviceId: deviceId);
    expect(
      acknowledgements.filter,
      'agrimind/v1/farms/$farmId/devices/$deviceId/acks/+',
    );
    expect(await repository.publish(command()), isTrue);
    expect(
      publisher.topic,
      'agrimind/v1/farms/$farmId/devices/$deviceId/commands/pump',
    );
    expect(jsonDecode(publisher.payload!)['command_id'], commandId);
    expect(await repository.publish(command(farm: deviceId)), isFalse);
    expect(publisher.publishes, 1);
  });

  test(
    'requires both channels and drops invalid acknowledgement input',
    () async {
      final publisher = FakeCommandWire();
      final acknowledgements = FakeAckWire();
      final repository = MqttManualIrrigationRepository(
        commandClient: publisher,
        acknowledgementClient: acknowledgements,
      );
      final events = <IrrigationRepositoryEvent>[];
      final subscription = repository.events.listen(events.add);
      await repository.connect(farmId: farmId, deviceId: deviceId);
      publisher.connections.add(WireConnectionEvent.connected);
      acknowledgements.connections.add(WireConnectionEvent.connected);
      acknowledgements.inbound
        ..add(const WireMessage(topic: 'bad/topic', payload: '{}'))
        ..add(
          WireMessage(
            topic:
                'agrimind/v1/farms/$farmId/devices/$deviceId/acks/$commandId',
            payload: jsonEncode({
              'schema_version': 1,
              'acknowledgement_id': '44444444-4444-4444-8444-444444444444',
              'command_id': commandId,
              'farm_id': farmId,
              'device_id': deviceId,
              'status': 'accepted',
              'occurred_at': '2026-09-24T08:00:01Z',
              'pump_state': true,
            }),
          ),
        );
      await pumpEventQueue();
      expect(
        events.whereType<IrrigationConnectionChanged>().last.phase.name,
        'connected',
      );
      expect(
        events.whereType<IrrigationAcknowledgementReceived>(),
        hasLength(1),
      );
      await subscription.cancel();
    },
  );
}
