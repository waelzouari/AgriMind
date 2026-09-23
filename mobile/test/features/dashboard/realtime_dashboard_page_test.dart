import 'dart:async';

import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/dashboard/application/dashboard_controller.dart';
import 'package:agrimind/features/dashboard/application/device_repository.dart';
import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/dashboard/domain/device.dart';
import 'package:agrimind/features/dashboard/domain/telemetry_reading.dart';
import 'package:agrimind/features/dashboard/presentation/dashboard_session.dart';
import 'package:agrimind/features/dashboard/presentation/realtime_dashboard_page.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_authentication_repository.dart';

const farm = Farm(
  id: 'efe00b4d-01e6-4565-8d86-18ba27f76666',
  name: 'sfax farm',
);
const deviceId = '4b9b0c3e-e810-4225-93d8-fd69523a295e';

final class DeviceRepo implements DeviceRepository {
  @override
  Future<Device> findActiveDevice(String farmId) async =>
      Device(id: deviceId, farmId: farmId, label: 'sfax-edge-1');
}

final class TelemetryRepo implements TelemetryRepository {
  final stream = StreamController<TelemetryEvent>.broadcast();
  int disconnects = 0;
  @override
  Stream<TelemetryEvent> get events => stream.stream;
  @override
  Future<void> connect({
    required String farmId,
    required String deviceId,
  }) async {}
  @override
  Future<void> disconnect() async => disconnects++;
}

DashboardController makeController(TelemetryRepo repository) =>
    DashboardController(
      deviceRepository: DeviceRepo(),
      telemetryRepository: repository,
      staleAfter: const Duration(seconds: 30),
      clock: () => DateTime.parse('2026-09-23T18:01:00Z'),
      startFreshnessTimer: false,
    );

Widget app(Widget child) =>
    MaterialApp(theme: AgriMindTheme.light, home: child);

void main() {
  testWidgets('shows broker semantics and waiting state without device claim', (
    tester,
  ) async {
    final authRepo = FakeAuthenticationRepository();
    final telemetry = TelemetryRepo();
    final controller = makeController(telemetry);
    await controller.start(farm.id);
    telemetry.stream.add(
      const TelemetryConnectionChanged(MqttConnectionPhase.connected),
    );
    await tester.pumpWidget(
      app(
        RealtimeDashboardPage(
          authentication: AuthenticationController(authRepo),
          farm: farm,
          controller: controller,
        ),
      ),
    );
    await tester.pump();
    expect(find.text('MQTT connecté'), findsOneWidget);
    expect(find.text('En attente des premières mesures'), findsOneWidget);
    expect(find.textContaining('appareil en ligne'), findsNothing);
    controller.dispose();
    await authRepo.close();
  });

  testWidgets('renders only received metrics and their freshness', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 568));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final authRepo = FakeAuthenticationRepository();
    final telemetry = TelemetryRepo();
    final controller = makeController(telemetry);
    await controller.start(farm.id);
    telemetry.stream.add(
      TelemetryReceived(
        TelemetryReading(
          messageId: '33333333-3333-4333-8333-333333333333',
          farmId: farm.id,
          deviceId: deviceId,
          metric: TelemetryMetric.soilMoisture,
          value: 64,
          unit: '%',
          recordedAt: DateTime.parse('2026-09-23T18:00:00Z'),
          quality: TelemetryQuality.valid,
        ),
      ),
    );
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(1.2)),
        child: app(
          RealtimeDashboardPage(
            authentication: AuthenticationController(authRepo),
            farm: farm,
            controller: controller,
          ),
        ),
      ),
    );
    await tester.pump();
    expect(find.text('Humidité du sol'), findsOneWidget);
    expect(find.text('64'), findsOneWidget);
    expect(find.text('Données anciennes'), findsOneWidget);
    expect(find.text('Température'), findsNothing);
    expect(tester.takeException(), isNull);
    controller.dispose();
    await authRepo.close();
  });

  testWidgets('disposing authenticated dashboard disconnects MQTT', (
    tester,
  ) async {
    final authRepo = FakeAuthenticationRepository();
    final telemetry = TelemetryRepo();
    await tester.pumpWidget(
      app(
        DashboardSession(
          authentication: AuthenticationController(authRepo),
          farm: farm,
          controllerFactory: () => makeController(telemetry),
        ),
      ),
    );
    await tester.pump();
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
    expect(telemetry.disconnects, greaterThanOrEqualTo(2));
    await authRepo.close();
  });
}
