import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_controller.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_repository.dart';
import 'package:agrimind/features/irrigation/domain/command_acknowledgement.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_manual_irrigation_repository.dart';

const farmId = '22222222-2222-4222-8222-222222222222';
const deviceId = '33333333-3333-4333-8333-333333333333';
const userId = '44444444-4444-4444-8444-444444444444';
const commandId = '11111111-1111-4111-8111-111111111111';

CommandAcknowledgement acknowledgement(
  CommandAcknowledgementStatus status, {
  String id = '55555555-5555-4555-8555-555555555555',
  String command = commandId,
  String farm = farmId,
  String device = deviceId,
  String? reason,
  bool? pumpState,
}) => CommandAcknowledgement(
  acknowledgementId: id,
  commandId: command,
  farmId: farm,
  deviceId: device,
  status: status,
  occurredAt: DateTime.parse('2026-09-24T08:00:01Z'),
  reasonCode: reason,
  pumpState: pumpState,
);

ManualIrrigationController makeController(
  FakeManualIrrigationRepository repository, {
  Duration timeout = const Duration(seconds: 15),
}) => ManualIrrigationController(
  repository: repository,
  acknowledgementTimeout: timeout,
  completionGrace: const Duration(seconds: 30),
  clock: () => DateTime.parse('2026-09-24T08:00:00Z'),
  commandIdFactory: () => commandId,
);

Future<ManualIrrigationController> connected(
  FakeManualIrrigationRepository repository, {
  Duration timeout = const Duration(seconds: 15),
}) async {
  final controller = makeController(repository, timeout: timeout);
  await controller.start(
    farmId: farmId,
    deviceId: deviceId,
    requestedBy: userId,
  );
  repository.controller.add(
    const IrrigationConnectionChanged(MqttConnectionPhase.connected),
  );
  await pumpEventQueue();
  return controller;
}

void main() {
  test(
    'one submit creates one correlated command and blocks duplicates',
    () async {
      final repository = FakeManualIrrigationRepository();
      final controller = await connected(repository);
      expect(await controller.submit(300), isTrue);
      expect(await controller.submit(300), isFalse);
      expect(repository.publishCalls, 1);
      expect(repository.publishedCommand?.commandId, commandId);
      expect(repository.publishedCommand?.requestedBy, userId);
      expect(
        repository.publishedCommand?.expiresAt,
        DateTime.parse('2026-09-24T08:00:15Z'),
      );
      expect(controller.phase, ManualIrrigationPhase.awaitingAcknowledgement);
      controller.dispose();
    },
  );

  test('only correlated ACKs drive accepted then completed', () async {
    final repository = FakeManualIrrigationRepository();
    final controller = await connected(repository);
    await controller.submit(60);
    repository.controller.add(
      IrrigationAcknowledgementReceived(
        acknowledgement(
          CommandAcknowledgementStatus.accepted,
          command: deviceId,
          pumpState: true,
        ),
      ),
    );
    await pumpEventQueue();
    expect(controller.phase, ManualIrrigationPhase.awaitingAcknowledgement);
    repository.controller.add(
      IrrigationAcknowledgementReceived(
        acknowledgement(CommandAcknowledgementStatus.accepted, pumpState: true),
      ),
    );
    await pumpEventQueue();
    expect(controller.phase, ManualIrrigationPhase.accepted);
    repository.controller.add(
      IrrigationAcknowledgementReceived(
        acknowledgement(
          CommandAcknowledgementStatus.completed,
          id: '66666666-6666-4666-8666-666666666666',
          pumpState: false,
        ),
      ),
    );
    await pumpEventQueue();
    expect(controller.phase, ManualIrrigationPhase.completed);
    expect(controller.acknowledgement?.pumpState, isFalse);
    controller.dispose();
  });

  test('rejection is terminal and duplicate ACK is idempotent', () async {
    final repository = FakeManualIrrigationRepository();
    final controller = await connected(repository);
    await controller.submit(60);
    final rejected = acknowledgement(
      CommandAcknowledgementStatus.rejected,
      reason: 'tank_level_low',
    );
    repository.controller.add(IrrigationAcknowledgementReceived(rejected));
    repository.controller.add(IrrigationAcknowledgementReceived(rejected));
    await pumpEventQueue();
    expect(controller.phase, ManualIrrigationPhase.rejected);
    expect(controller.acknowledgement?.reasonCode, 'tank_level_low');
    controller.dispose();
  });

  test('PUBACK failure and ACK timeout never claim physical success', () async {
    final failedRepository = FakeManualIrrigationRepository()
      ..publishConfirmed = false;
    final failed = await connected(failedRepository);
    expect(await failed.submit(60), isFalse);
    expect(failed.phase, ManualIrrigationPhase.failed);
    expect(failed.acknowledgement, isNull);
    failed.dispose();

    final timeoutRepository = FakeManualIrrigationRepository();
    final timedOut = await connected(
      timeoutRepository,
      timeout: const Duration(milliseconds: 1),
    );
    await timedOut.submit(60);
    await Future<void>.delayed(const Duration(milliseconds: 5));
    expect(timedOut.phase, ManualIrrigationPhase.timedOut);
    timedOut.dispose();
  });

  test('reconnect does not republish or replace the pending command', () async {
    final repository = FakeManualIrrigationRepository();
    final controller = await connected(repository);
    await controller.submit(60);
    repository.controller
      ..add(const IrrigationConnectionChanged(MqttConnectionPhase.reconnecting))
      ..add(const IrrigationConnectionChanged(MqttConnectionPhase.connected));
    await pumpEventQueue();
    expect(repository.publishCalls, 1);
    expect(controller.command?.commandId, commandId);
    expect(controller.phase, ManualIrrigationPhase.awaitingAcknowledgement);
    controller.dispose();
  });
}
