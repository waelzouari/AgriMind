import 'dart:async';

import 'package:agrimind/features/dashboard/application/dashboard_controller.dart';
import 'package:agrimind/features/dashboard/application/device_repository.dart';
import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/dashboard/domain/device.dart';
import 'package:agrimind/features/dashboard/domain/telemetry_reading.dart';
import 'package:flutter_test/flutter_test.dart';

const farmId = 'efe00b4d-01e6-4565-8d86-18ba27f76666';
const deviceId = '4b9b0c3e-e810-4225-93d8-fd69523a295e';

final class FakeDeviceRepository implements DeviceRepository {
  @override
  Future<Device> findActiveDevice(String farmId) async =>
      Device(id: deviceId, farmId: farmId, label: 'sfax-edge-1');
}

final class FakeTelemetryRepository implements TelemetryRepository {
  final controller = StreamController<TelemetryEvent>.broadcast();
  int disconnects = 0;
  String? connectedFarm;
  String? connectedDevice;
  @override
  Stream<TelemetryEvent> get events => controller.stream;
  @override
  Future<void> connect({
    required String farmId,
    required String deviceId,
  }) async {
    connectedFarm = farmId;
    connectedDevice = deviceId;
  }

  @override
  Future<void> disconnect() async => disconnects++;
}

TelemetryReading reading(
  TelemetryMetric metric, {
  String? id,
  String time = '2026-09-23T18:00:00Z',
  double value = 1,
}) => TelemetryReading(
  messageId:
      id ??
      switch (metric) {
        TelemetryMetric.temperature => '11111111-1111-4111-8111-111111111111',
        TelemetryMetric.humidity => '22222222-2222-4222-8222-222222222222',
        TelemetryMetric.soilMoisture => '33333333-3333-4333-8333-333333333333',
        TelemetryMetric.tankLevel => '44444444-4444-4444-8444-444444444444',
      },
  farmId: farmId,
  deviceId: deviceId,
  metric: metric,
  value: value,
  unit: metric.unit,
  recordedAt: DateTime.parse(time),
  quality: TelemetryQuality.valid,
);

void main() {
  late FakeTelemetryRepository repository;
  late DashboardController controller;
  setUp(() {
    repository = FakeTelemetryRepository();
    controller = DashboardController(
      deviceRepository: FakeDeviceRepository(),
      telemetryRepository: repository,
      staleAfter: const Duration(seconds: 30),
      clock: () => DateTime.parse('2026-09-23T18:00:20Z'),
      startFreshnessTimer: false,
    );
  });
  tearDown(() => controller.dispose());

  test(
    'resolves active device before opening MQTT and tracks lifecycle',
    () async {
      await controller.start(farmId);
      expect(repository.connectedFarm, farmId);
      expect(repository.connectedDevice, deviceId);
      repository.controller.add(
        const TelemetryConnectionChanged(MqttConnectionPhase.connected),
      );
      await pumpEventQueue();
      expect(controller.phase, MqttConnectionPhase.connected);
      repository.controller.add(
        const TelemetryConnectionChanged(MqttConnectionPhase.reconnecting),
      );
      await pumpEventQueue();
      expect(controller.phase, MqttConnectionPhase.reconnecting);
    },
  );

  test('keeps four metrics and ignores duplicate and older messages', () async {
    await controller.start(farmId);
    for (final metric in TelemetryMetric.values) {
      repository.controller.add(TelemetryReceived(reading(metric, value: 10)));
    }
    await pumpEventQueue();
    expect(controller.readings, hasLength(4));

    repository.controller.add(
      TelemetryReceived(reading(TelemetryMetric.temperature, value: 99)),
    );
    repository.controller.add(
      TelemetryReceived(
        reading(
          TelemetryMetric.temperature,
          id: '55555555-5555-4555-8555-555555555555',
          time: '2026-09-23T17:59:59Z',
          value: 88,
        ),
      ),
    );
    await pumpEventQueue();
    expect(controller.readings[TelemetryMetric.temperature]?.value, 10);
  });

  test('marks old telemetry stale and clears state on stop', () async {
    await controller.start(farmId);
    final old = reading(
      TelemetryMetric.temperature,
      time: '2026-09-23T17:59:00Z',
    );
    repository.controller.add(TelemetryReceived(old));
    await pumpEventQueue();
    expect(controller.isStale(old), isTrue);
    await controller.stop();
    expect(controller.readings, isEmpty);
    expect(controller.phase, MqttConnectionPhase.idle);
    expect(repository.disconnects, greaterThanOrEqualTo(2));
  });
}
