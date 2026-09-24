import 'dart:convert';

import 'package:agrimind/features/irrigation/domain/command_acknowledgement.dart';
import 'package:flutter_test/flutter_test.dart';

const commandId = '11111111-1111-4111-8111-111111111111';
const farmId = '22222222-2222-4222-8222-222222222222';
const deviceId = '33333333-3333-4333-8333-333333333333';

Map<String, Object?> ack({String status = 'accepted', String? reasonCode}) => {
  'schema_version': 1,
  'acknowledgement_id': '44444444-4444-4444-8444-444444444444',
  'command_id': commandId,
  'farm_id': farmId,
  'device_id': deviceId,
  'status': status,
  'occurred_at': '2026-09-24T08:00:01Z',
  // ignore: use_null_aware_elements
  if (reasonCode != null) 'reason_code': reasonCode,
  'pump_state': status == 'accepted',
};

CommandAcknowledgement? decode(Map<String, Object?> value) =>
    CommandAcknowledgement.tryDecode(
      jsonEncode(value),
      topicCommandId: commandId,
      expectedFarmId: farmId,
      expectedDeviceId: deviceId,
    );

void main() {
  test('accepts a correlated canonical acknowledgement', () {
    final value = decode(ack());
    expect(value?.status, CommandAcknowledgementStatus.accepted);
    expect(value?.pumpState, isTrue);
  });

  test('rejects malformed, cross-target and uncorrelated acknowledgements', () {
    expect(decode({...ack(), 'unexpected': true}), isNull);
    expect(decode({...ack(), 'farm_id': deviceId}), isNull);
    expect(decode({...ack(), 'command_id': deviceId}), isNull);
    expect(
      decode({...ack(), 'occurred_at': '2026-09-24T08:00:01+00:00'}),
      isNull,
    );
  });

  test('requires a safe reason only for rejected or failed statuses', () {
    expect(decode(ack(status: 'rejected')), isNull);
    expect(
      decode(ack(status: 'failed', reasonCode: 'controller_fault')),
      isNotNull,
    );
    expect(decode(ack(reasonCode: 'not_allowed')), isNull);
    expect(decode(ack(status: 'rejected', reasonCode: 'Not Safe')), isNull);
  });
}
