import 'dart:convert';

enum CommandAcknowledgementStatus { accepted, rejected, completed, failed }

final class CommandAcknowledgement {
  const CommandAcknowledgement({
    required this.acknowledgementId,
    required this.commandId,
    required this.farmId,
    required this.deviceId,
    required this.status,
    required this.occurredAt,
    this.reasonCode,
    this.pumpState,
  });

  static const _keys = {
    'schema_version',
    'acknowledgement_id',
    'command_id',
    'farm_id',
    'device_id',
    'status',
    'occurred_at',
    'reason_code',
    'pump_state',
  };
  static final _uuid = RegExp(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
  );
  static final _reason = RegExp(r'^[a-z0-9]+(?:_[a-z0-9]+)*$');

  final String acknowledgementId;
  final String commandId;
  final String farmId;
  final String deviceId;
  final CommandAcknowledgementStatus status;
  final DateTime occurredAt;
  final String? reasonCode;
  final bool? pumpState;

  static CommandAcknowledgement? tryDecode(
    String payload, {
    required String topicCommandId,
    required String expectedFarmId,
    required String expectedDeviceId,
  }) {
    try {
      final value = jsonDecode(payload);
      if (value is! Map<String, dynamic> ||
          value.keys.toSet().difference(_keys).isNotEmpty ||
          value['schema_version'] != 1) {
        return null;
      }
      const required = {
        'schema_version',
        'acknowledgement_id',
        'command_id',
        'farm_id',
        'device_id',
        'status',
        'occurred_at',
      };
      if (required.difference(value.keys.toSet()).isNotEmpty) return null;
      final acknowledgementId = value['acknowledgement_id'];
      final commandId = value['command_id'];
      final farmId = value['farm_id'];
      final deviceId = value['device_id'];
      final occurredAtText = value['occurred_at'];
      final reasonCode = value['reason_code'];
      final pumpState = value['pump_state'];
      if (acknowledgementId is! String ||
          !_canonicalUuid(acknowledgementId) ||
          commandId is! String ||
          !_canonicalUuid(commandId) ||
          commandId != topicCommandId ||
          farmId != expectedFarmId ||
          deviceId != expectedDeviceId ||
          occurredAtText is! String ||
          !occurredAtText.endsWith('Z') ||
          (pumpState != null && pumpState is! bool)) {
        return null;
      }
      final occurredAt = DateTime.tryParse(occurredAtText);
      final status = switch (value['status']) {
        'accepted' => CommandAcknowledgementStatus.accepted,
        'rejected' => CommandAcknowledgementStatus.rejected,
        'completed' => CommandAcknowledgementStatus.completed,
        'failed' => CommandAcknowledgementStatus.failed,
        _ => null,
      };
      if (occurredAt == null || !occurredAt.isUtc || status == null) {
        return null;
      }
      final needsReason =
          status == CommandAcknowledgementStatus.rejected ||
          status == CommandAcknowledgementStatus.failed;
      if (needsReason != (reasonCode != null) ||
          (reasonCode != null &&
              (reasonCode is! String ||
                  reasonCode.length > 64 ||
                  !_reason.hasMatch(reasonCode)))) {
        return null;
      }
      return CommandAcknowledgement(
        acknowledgementId: acknowledgementId,
        commandId: commandId,
        farmId: farmId as String,
        deviceId: deviceId as String,
        status: status,
        occurredAt: occurredAt,
        reasonCode: reasonCode as String?,
        pumpState: pumpState as bool?,
      );
    } on FormatException {
      return null;
    }
  }

  static bool _canonicalUuid(String value) =>
      value != '00000000-0000-0000-0000-000000000000' && _uuid.hasMatch(value);
}
