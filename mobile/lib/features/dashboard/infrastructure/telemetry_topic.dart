import 'package:agrimind/features/dashboard/domain/telemetry_reading.dart';

final class TelemetryTopic {
  const TelemetryTopic({required this.farmId, required this.deviceId});
  final String farmId;
  final String deviceId;

  String get prefix => 'agrimind/v1/farms/$farmId/devices/$deviceId';
  String get filter => '$prefix/telemetry/+';
  String metric(TelemetryMetric metric) =>
      '$prefix/telemetry/${metric.wireName}';

  TelemetryMetric? parse(String topic) {
    final suffix = '$prefix/telemetry/';
    if (!topic.startsWith(suffix)) return null;
    final value = topic.substring(suffix.length);
    if (value.contains('/')) return null;
    return TelemetryMetricWire.parse(value);
  }
}
