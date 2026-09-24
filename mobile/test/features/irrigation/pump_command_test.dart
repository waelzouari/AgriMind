import 'dart:convert';

import 'package:agrimind/features/irrigation/domain/pump_command.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('serializes the existing v1 ON contract exactly', () {
    final payload =
        jsonDecode(
              PumpCommand(
                commandId: '11111111-1111-4111-8111-111111111111',
                farmId: '22222222-2222-4222-8222-222222222222',
                deviceId: '33333333-3333-4333-8333-333333333333',
                durationSeconds: 300,
                issuedAt: DateTime.parse('2026-09-24T10:00:00+02:00'),
                expiresAt: DateTime.parse('2026-09-24T10:00:15+02:00'),
                requestedBy: '44444444-4444-4444-8444-444444444444',
              ).toJson(),
            )
            as Map<String, dynamic>;

    expect(payload, {
      'schema_version': 1,
      'command_id': '11111111-1111-4111-8111-111111111111',
      'farm_id': '22222222-2222-4222-8222-222222222222',
      'device_id': '33333333-3333-4333-8333-333333333333',
      'action': 'on',
      'issued_at': '2026-09-24T08:00:00.000Z',
      'expires_at': '2026-09-24T08:00:15.000Z',
      'requested_by': '44444444-4444-4444-8444-444444444444',
      'duration_seconds': 300,
    });
  });
}
