import 'package:agrimind/app/agrimind_app.dart';
import 'package:agrimind/core/config/app_config.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/dashboard/application/dashboard_controller.dart';
import 'package:agrimind/features/dashboard/application/device_repository.dart';
import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/dashboard/domain/device.dart';
import 'package:agrimind/features/dashboard/presentation/dashboard_session.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_controller.dart';
import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/weather/application/weather_controller.dart';
import 'package:flutter/widgets.dart';

import 'fake_farm_manager_repository.dart';
import 'fake_farm_repository.dart';
import 'fake_manual_irrigation_repository.dart';
import 'fake_weather_repository.dart';

const testConfig = AppConfig(
  supabaseUrl: 'https://project-ref.supabase.co',
  supabaseAnonKey: 'public-anon-placeholder',
  mqttHost: 'mqtt.example.com',
  telemetryMqttUsername: 'mobile-read-only',
  telemetryMqttPassword: 'test-placeholder', // pragma: allowlist secret
  commandMqttUsername: 'mobile-command',
  commandMqttPassword: 'test-placeholder', // pragma: allowlist secret
  ackMqttUsername: 'mobile-ack',
  ackMqttPassword: 'test-placeholder', // pragma: allowlist secret
);

Widget authTestApp(
  AuthenticationController controller, {
  FakeFarmRepository? farmRepository,
  DashboardControllerFactory? dashboardControllerFactory,
}) {
  final repository =
      farmRepository ??
      FakeFarmRepository(
        currentFarm: Farm(id: 'farm-a', name: 'Ferme A'),
      );
  return AgriMindApp(
    config: testConfig,
    authentication: controller,
    farmController: FarmController(repository),
    farmManagerRepository: FakeFarmManagerRepository(),
    dashboardControllerFactory:
        dashboardControllerFactory ??
        () => DashboardController(
          deviceRepository: _TestDeviceRepository(),
          telemetryRepository: _TestTelemetryRepository(),
          staleAfter: const Duration(seconds: 30),
          manualIrrigation: ManualIrrigationController(
            repository: FakeManualIrrigationRepository(),
            acknowledgementTimeout: const Duration(seconds: 15),
            completionGrace: const Duration(seconds: 30),
          ),
          startFreshnessTimer: false,
        ),
    weatherControllerFactory: () =>
        WeatherController(repository: FakeWeatherRepository()),
  );
}

final class _TestDeviceRepository implements DeviceRepository {
  @override
  Future<Device> findActiveDevice(String farmId) async => Device(
    id: '4b9b0c3e-e810-4225-93d8-fd69523a295e',
    farmId: farmId,
    label: 'test-device',
  );
}

final class _TestTelemetryRepository implements TelemetryRepository {
  @override
  Stream<TelemetryEvent> get events => const Stream.empty();
  @override
  Future<void> connect({
    required String farmId,
    required String deviceId,
  }) async {}
  @override
  Future<void> disconnect() async {}
}
