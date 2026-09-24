import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_controller.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_repository.dart';
import 'package:agrimind/features/irrigation/domain/command_acknowledgement.dart';
import 'package:agrimind/features/irrigation/presentation/manual_irrigation_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_manual_irrigation_repository.dart';

const commandId = '11111111-1111-4111-8111-111111111111';
const farmId = '22222222-2222-4222-8222-222222222222';
const deviceId = '33333333-3333-4333-8333-333333333333';

Future<
  ({
    ManualIrrigationController controller,
    FakeManualIrrigationRepository repository,
  })
>
makeController() async {
  final repository = FakeManualIrrigationRepository();
  final controller = ManualIrrigationController(
    repository: repository,
    acknowledgementTimeout: const Duration(seconds: 15),
    completionGrace: const Duration(seconds: 30),
    clock: () => DateTime.parse('2026-09-24T08:00:00Z'),
    commandIdFactory: () => commandId,
  );
  await controller.start(
    farmId: farmId,
    deviceId: deviceId,
    requestedBy: '44444444-4444-4444-8444-444444444444',
  );
  repository.controller.add(
    const IrrigationConnectionChanged(MqttConnectionPhase.connected),
  );
  return (controller: controller, repository: repository);
}

Widget app(ManualIrrigationController controller) => MaterialApp(
  theme: AgriMindTheme.light,
  home: Scaffold(
    body: SingleChildScrollView(
      child: ManualIrrigationCard(controller: controller),
    ),
  ),
);

void main() {
  testWidgets(
    'requires confirmation and never equates PUBACK with pump success',
    (tester) async {
      final state = await makeController();
      await tester.pumpWidget(app(state.controller));
      await tester.pump();
      await tester.tap(find.text('Demander l’irrigation'));
      await tester.pumpAndSettle();
      expect(find.text('Confirmer la demande'), findsOneWidget);
      await tester.tap(find.text('Envoyer la demande'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(state.repository.publishCalls, 1);
      expect(find.text('En attente de l’edge'), findsOneWidget);
      expect(find.textContaining('pompe a été confirmée active'), findsNothing);
      state.controller.dispose();
    },
  );

  testWidgets('renders edge acceptance and completion honestly on narrow UI', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 568));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final state = await makeController();
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(1.2)),
        child: app(state.controller),
      ),
    );
    await tester.pump();
    await state.controller.submit(60);
    state.repository.controller.add(
      IrrigationAcknowledgementReceived(
        CommandAcknowledgement(
          acknowledgementId: '55555555-5555-4555-8555-555555555555',
          commandId: commandId,
          farmId: farmId,
          deviceId: deviceId,
          status: CommandAcknowledgementStatus.accepted,
          occurredAt: DateTime.parse('2026-09-24T08:00:01Z'),
          pumpState: true,
        ),
      ),
    );
    await tester.pump();
    expect(find.text('Commande acceptée par l’edge'), findsOneWidget);
    expect(find.textContaining('confirmée active'), findsOneWidget);
    expect(tester.takeException(), isNull);
    state.controller.dispose();
  });
}
