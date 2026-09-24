import 'dart:convert';

final class PumpCommand {
  const PumpCommand({
    required this.commandId,
    required this.farmId,
    required this.deviceId,
    required this.durationSeconds,
    required this.issuedAt,
    required this.expiresAt,
    required this.requestedBy,
  });

  final String commandId;
  final String farmId;
  final String deviceId;
  final int durationSeconds;
  final DateTime issuedAt;
  final DateTime expiresAt;
  final String requestedBy;

  String toJson() => jsonEncode({
    'schema_version': 1,
    'command_id': commandId,
    'farm_id': farmId,
    'device_id': deviceId,
    'action': 'on',
    'issued_at': _utc(issuedAt),
    'expires_at': _utc(expiresAt),
    'requested_by': requestedBy,
    'duration_seconds': durationSeconds,
  });

  static String _utc(DateTime value) => value.toUtc().toIso8601String();
}
