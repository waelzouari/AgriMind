import 'package:agrimind/features/dashboard/domain/telemetry_reading.dart';
import 'package:agrimind/features/dashboard/infrastructure/telemetry_topic.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const topic = TelemetryTopic(farmId: 'farm-a', deviceId: 'device-a');
  test('builds the exact scoped filter and canonical metric topics', () {
    expect(
      topic.filter,
      'agrimind/v1/farms/farm-a/devices/device-a/telemetry/+',
    );
    expect(
      topic.metric(TelemetryMetric.soilMoisture),
      'agrimind/v1/farms/farm-a/devices/device-a/telemetry/soil_moisture',
    );
  });
  test('rejects topics outside the exact identity and metric set', () {
    expect(
      topic.parse('${topic.prefix}/telemetry/temperature'),
      TelemetryMetric.temperature,
    );
    expect(topic.parse('${topic.prefix}/status/device'), isNull);
    expect(
      topic.parse(
        'agrimind/v1/farms/other/devices/device-a/telemetry/temperature',
      ),
      isNull,
    );
    expect(topic.parse('${topic.prefix}/telemetry/temperature/extra'), isNull);
  });
}
