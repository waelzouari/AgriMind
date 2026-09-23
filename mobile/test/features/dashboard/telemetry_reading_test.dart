import 'dart:convert';

import 'package:agrimind/features/dashboard/domain/telemetry_reading.dart';
import 'package:flutter_test/flutter_test.dart';

const farmId = 'efe00b4d-01e6-4565-8d86-18ba27f76666';
const deviceId = '4b9b0c3e-e810-4225-93d8-fd69523a295e';

Map<String, Object> payload({
  String messageId = '33333333-3333-4333-8333-333333333333',
  String farm = farmId,
  String device = deviceId,
  String metric = 'temperature',
  Object value = 26.5,
  String unit = '°C',
  String recordedAt = '2026-09-23T18:00:00.000Z',
  String quality = 'valid',
}) => {
  'schema_version': 1,
  'message_id': messageId,
  'farm_id': farm,
  'device_id': device,
  'metric': metric,
  'value': value,
  'unit': unit,
  'recorded_at': recordedAt,
  'quality': quality,
};

void main() {
  test('decodes the canonical v1 payload', () {
    final reading = TelemetryReading.tryDecode(
      jsonEncode(payload()),
      expectedFarmId: farmId,
      expectedDeviceId: deviceId,
      topicMetric: TelemetryMetric.temperature,
    );
    expect(reading?.value, 26.5);
    expect(reading?.quality, TelemetryQuality.valid);
  });

  test('rejects malformed, extra, wrong identity, topic and unit payloads', () {
    final cases = <Map<String, Object>>[
      {...payload(), 'extra': true},
      payload(farm: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
      payload(device: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
      payload(unit: '%'),
      payload(messageId: 'not-a-uuid'),
      payload(recordedAt: '2026-09-23T18:00:00+01:00'),
    ];
    for (final value in cases) {
      expect(
        TelemetryReading.tryDecode(
          jsonEncode(value),
          expectedFarmId: farmId,
          expectedDeviceId: deviceId,
          topicMetric: TelemetryMetric.temperature,
        ),
        isNull,
      );
    }
    expect(
      TelemetryReading.tryDecode(
        '{bad',
        expectedFarmId: farmId,
        expectedDeviceId: deviceId,
        topicMetric: TelemetryMetric.temperature,
      ),
      isNull,
    );
    expect(
      TelemetryReading.tryDecode(
        jsonEncode(payload()),
        expectedFarmId: farmId,
        expectedDeviceId: deviceId,
        topicMetric: TelemetryMetric.humidity,
      ),
      isNull,
    );
  });

  test('enforces percentages and all metric/unit pairs', () {
    for (final entry in {
      TelemetryMetric.temperature: ('temperature', '°C', 22.0),
      TelemetryMetric.humidity: ('humidity', '%', 58.0),
      TelemetryMetric.soilMoisture: ('soil_moisture', '%', 64.0),
      TelemetryMetric.tankLevel: ('tank_level', 'cm', 78.0),
    }.entries) {
      expect(
        TelemetryReading.tryDecode(
          jsonEncode(
            payload(
              metric: entry.value.$1,
              unit: entry.value.$2,
              value: entry.value.$3,
            ),
          ),
          expectedFarmId: farmId,
          expectedDeviceId: deviceId,
          topicMetric: entry.key,
        ),
        isNotNull,
      );
    }
    expect(
      TelemetryReading.tryDecode(
        jsonEncode(payload(metric: 'humidity', unit: '%', value: 101)),
        expectedFarmId: farmId,
        expectedDeviceId: deviceId,
        topicMetric: TelemetryMetric.humidity,
      ),
      isNull,
    );
  });
}
