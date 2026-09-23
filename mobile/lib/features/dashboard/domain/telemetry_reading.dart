import 'dart:convert';

enum TelemetryMetric { temperature, humidity, soilMoisture, tankLevel }

extension TelemetryMetricWire on TelemetryMetric {
  String get wireName => switch (this) {
    TelemetryMetric.temperature => 'temperature',
    TelemetryMetric.humidity => 'humidity',
    TelemetryMetric.soilMoisture => 'soil_moisture',
    TelemetryMetric.tankLevel => 'tank_level',
  };

  String get unit => switch (this) {
    TelemetryMetric.temperature => '°C',
    TelemetryMetric.humidity || TelemetryMetric.soilMoisture => '%',
    TelemetryMetric.tankLevel => 'cm',
  };

  static TelemetryMetric? parse(String value) => switch (value) {
    'temperature' => TelemetryMetric.temperature,
    'humidity' => TelemetryMetric.humidity,
    'soil_moisture' => TelemetryMetric.soilMoisture,
    'tank_level' => TelemetryMetric.tankLevel,
    _ => null,
  };
}

enum TelemetryQuality { valid, estimated }

final class TelemetryReading {
  const TelemetryReading({
    required this.messageId,
    required this.farmId,
    required this.deviceId,
    required this.metric,
    required this.value,
    required this.unit,
    required this.recordedAt,
    required this.quality,
  });

  static const _keys = {
    'schema_version',
    'message_id',
    'farm_id',
    'device_id',
    'metric',
    'value',
    'unit',
    'recorded_at',
    'quality',
  };
  static final _uuid = RegExp(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
  );

  final String messageId;
  final String farmId;
  final String deviceId;
  final TelemetryMetric metric;
  final double value;
  final String unit;
  final DateTime recordedAt;
  final TelemetryQuality quality;

  static TelemetryReading? tryDecode(
    String payload, {
    required String expectedFarmId,
    required String expectedDeviceId,
    required TelemetryMetric topicMetric,
  }) {
    try {
      final decoded = jsonDecode(payload);
      if (decoded is! Map<String, dynamic> ||
          decoded.keys.toSet().difference(_keys).isNotEmpty ||
          _keys.difference(decoded.keys.toSet()).isNotEmpty ||
          decoded['schema_version'] != 1) {
        return null;
      }
      final messageId = decoded['message_id'];
      final farmId = decoded['farm_id'];
      final deviceId = decoded['device_id'];
      final metricName = decoded['metric'];
      final value = decoded['value'];
      final unit = decoded['unit'];
      final recordedAtText = decoded['recorded_at'];
      final qualityText = decoded['quality'];
      if (messageId is! String ||
          !_isCanonicalUuid(messageId) ||
          farmId is! String ||
          !_isCanonicalUuid(farmId) ||
          deviceId is! String ||
          !_isCanonicalUuid(deviceId) ||
          farmId != expectedFarmId ||
          deviceId != expectedDeviceId ||
          metricName is! String ||
          unit is! String ||
          recordedAtText is! String ||
          !recordedAtText.endsWith('Z') ||
          value is! num ||
          !value.isFinite) {
        return null;
      }
      final metric = TelemetryMetricWire.parse(metricName);
      final recordedAt = DateTime.tryParse(recordedAtText);
      final quality = switch (qualityText) {
        'valid' => TelemetryQuality.valid,
        'estimated' => TelemetryQuality.estimated,
        _ => null,
      };
      if (metric == null ||
          metric != topicMetric ||
          unit != metric.unit ||
          recordedAt == null ||
          !recordedAt.isUtc ||
          quality == null) {
        return null;
      }
      if ((metric == TelemetryMetric.humidity ||
              metric == TelemetryMetric.soilMoisture) &&
          (value < 0 || value > 100)) {
        return null;
      }
      return TelemetryReading(
        messageId: messageId,
        farmId: farmId,
        deviceId: deviceId,
        metric: metric,
        value: value.toDouble(),
        unit: unit,
        recordedAt: recordedAt,
        quality: quality,
      );
    } on FormatException {
      return null;
    }
  }

  static bool _isCanonicalUuid(String value) =>
      value != '00000000-0000-0000-0000-000000000000' && _uuid.hasMatch(value);
}
