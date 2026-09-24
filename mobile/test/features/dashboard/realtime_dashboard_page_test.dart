import 'dart:async';

import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/domain/auth_session.dart';
import 'package:agrimind/features/dashboard/application/dashboard_controller.dart';
import 'package:agrimind/features/dashboard/application/device_repository.dart';
import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/dashboard/domain/device.dart';
import 'package:agrimind/features/dashboard/domain/telemetry_reading.dart';
import 'package:agrimind/features/dashboard/presentation/dashboard_session.dart';
import 'package:agrimind/features/dashboard/presentation/realtime_dashboard_page.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_controller.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/weather/application/weather_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_authentication_repository.dart';
import '../../helpers/fake_farm_manager_repository.dart';
import '../../helpers/fake_manual_irrigation_repository.dart';
import '../../helpers/fake_weather_repository.dart';

final farm = Farm(
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
  int connects = 0;
  int disconnects = 0;
  @override
  Stream<TelemetryEvent> get events => stream.stream;
  @override
  Future<void> connect({
    required String farmId,
    required String deviceId,
  }) async => connects++;
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
      manualIrrigation: ManualIrrigationController(
        repository: FakeManualIrrigationRepository(),
        acknowledgementTimeout: const Duration(seconds: 15),
        completionGrace: const Duration(seconds: 30),
      ),
    );

Widget app(Widget child) =>
    MaterialApp(theme: AgriMindTheme.light, home: child);

WeatherController makeWeatherController() =>
    WeatherController(repository: FakeWeatherRepository());

void main() {
  testWidgets('shows broker semantics and waiting state without device claim', (
    tester,
  ) async {
    final authRepo = FakeAuthenticationRepository();
    final telemetry = TelemetryRepo();
    final controller = makeController(telemetry);
    var farmNavigationCalls = 0;
    await controller.start(farm.id, requestedBy: farm.id);
    telemetry.stream.add(
      const TelemetryConnectionChanged(MqttConnectionPhase.connected),
    );
    await tester.pumpWidget(
      app(
        RealtimeDashboardPage(
          authentication: AuthenticationController(authRepo),
          farm: farm,
          controller: controller,
          weatherController: makeWeatherController(),
          onOpenFarm: () => farmNavigationCalls += 1,
        ),
      ),
    );
    await tester.pump();
    expect(find.text('MQTT connecté'), findsOneWidget);
    expect(find.text('En attente des premières mesures'), findsOneWidget);
    expect(find.textContaining('appareil en ligne'), findsNothing);
    await tester.tap(find.text('Ferme'));
    expect(farmNavigationCalls, 1);
    final sensorY = tester.getTopLeft(find.text('Capteurs en direct')).dy;
    final weatherY = tester.getTopLeft(find.text('Météo')).dy;
    final irrigationY = tester.getTopLeft(find.text('Irrigation manuelle')).dy;
    expect(sensorY, lessThan(weatherY));
    expect(weatherY, lessThan(irrigationY));
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
    await controller.start(farm.id, requestedBy: farm.id);
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
            weatherController: makeWeatherController(),
            onOpenFarm: () {},
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
    final authRepo = FakeAuthenticationRepository(
      restoredSession: const AuthSession(
        userId: '44444444-4444-4444-8444-444444444444',
        email: 'farmer@example.com',
      ),
    );
    final authentication = AuthenticationController(authRepo);
    await authentication.restoreSession();
    final telemetry = TelemetryRepo();
    await tester.pumpWidget(
      app(
        DashboardSession(
          authentication: authentication,
          farm: farm,
          controllerFactory: () => makeController(telemetry),
          farmManagerRepository: FakeFarmManagerRepository(),
          weatherControllerFactory: makeWeatherController,
        ),
      ),
    );
    await tester.pump();
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
    expect(telemetry.disconnects, greaterThanOrEqualTo(2));
    await authRepo.close();
  });

  testWidgets('coordinate changes reload weather without reconnecting MQTT', (
    tester,
  ) async {
    final authRepo = FakeAuthenticationRepository(
      restoredSession: const AuthSession(
        userId: '44444444-4444-4444-8444-444444444444',
        email: 'farmer@example.com',
      ),
    );
    final authentication = AuthenticationController(authRepo);
    await authentication.restoreSession();
    final telemetry = TelemetryRepo();
    final weatherRepository = FakeWeatherRepository();
    WeatherController makeWeather() =>
        WeatherController(repository: weatherRepository);
    final initialFarm = Farm(
      id: farm.id,
      name: farm.name,
      latitude: 34,
      longitude: 10,
    );

    await tester.pumpWidget(
      app(
        DashboardSession(
          authentication: authentication,
          farm: initialFarm,
          controllerFactory: () => makeController(telemetry),
          farmManagerRepository: FakeFarmManagerRepository(),
          weatherControllerFactory: makeWeather,
        ),
      ),
    );
    await tester.pump();
    expect(weatherRepository.calls, 1);
    expect(telemetry.connects, 1);

    await tester.pumpWidget(
      app(
        DashboardSession(
          authentication: authentication,
          farm: Farm(id: farm.id, name: farm.name, latitude: 35, longitude: 11),
          controllerFactory: () => makeController(telemetry),
          farmManagerRepository: FakeFarmManagerRepository(),
          weatherControllerFactory: makeWeather,
        ),
      ),
    );
    await tester.pump();

    expect(weatherRepository.calls, 2);
    expect(telemetry.connects, 1);
    await tester.pumpWidget(const SizedBox());
    await authRepo.close();
  });
}
