import 'package:agrimind/app/agrimind_app.dart';
import 'package:agrimind/core/config/app_config.dart';
import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/infrastructure/supabase_authentication_repository.dart';
import 'package:agrimind/features/dashboard/application/dashboard_controller.dart';
import 'package:agrimind/features/dashboard/infrastructure/mqtt_telemetry_repository.dart';
import 'package:agrimind/features/dashboard/infrastructure/mqtt_wire_client.dart';
import 'package:agrimind/features/dashboard/infrastructure/supabase_device_repository.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_controller.dart';
import 'package:agrimind/features/irrigation/infrastructure/mqtt_command_wire_client.dart';
import 'package:agrimind/features/irrigation/infrastructure/mqtt_manual_irrigation_repository.dart';
import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:agrimind/features/onboarding/infrastructure/supabase_farm_repository.dart';
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final config = AppConfig.fromEnvironment();
  try {
    config.validate();
    await Supabase.initialize(
      url: config.supabaseUrl,
      publishableKey: config.supabaseAnonKey,
    );
    final client = Supabase.instance.client;
    final repository = SupabaseAuthenticationRepository(client);
    runApp(
      AgriMindApp(
        config: config,
        authentication: AuthenticationController(repository),
        farmController: FarmController(SupabaseFarmRepository(client)),
        dashboardControllerFactory: () => DashboardController(
          deviceRepository: SupabaseDeviceRepository(client),
          telemetryRepository: MqttTelemetryRepository(
            PahoStyleMqttWireClient(
              host: config.mqttHost,
              port: config.mqttPort,
              username: config.telemetryMqttUsername,
              password: config.telemetryMqttPassword,
            ),
          ),
          staleAfter: Duration(seconds: config.telemetryStaleSeconds),
          manualIrrigation: ManualIrrigationController(
            repository: MqttManualIrrigationRepository(
              commandClient: MqttCommandPublisherClient(
                host: config.mqttHost,
                port: config.mqttPort,
                username: config.commandMqttUsername,
                password: config.commandMqttPassword,
              ),
              acknowledgementClient: PahoStyleMqttWireClient(
                host: config.mqttHost,
                port: config.mqttPort,
                username: config.ackMqttUsername,
                password: config.ackMqttPassword,
              ),
            ),
            acknowledgementTimeout: Duration(
              seconds: config.commandAcknowledgementTimeoutSeconds,
            ),
            completionGrace: Duration(
              seconds: config.commandCompletionGraceSeconds,
            ),
          ),
        ),
      ),
    );
  } on Object {
    runApp(const _ConfigurationErrorApp());
  }
}

class _ConfigurationErrorApp extends StatelessWidget {
  const _ConfigurationErrorApp();

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AGRIMIND',
      debugShowCheckedModeBanner: false,
      theme: AgriMindTheme.light,
      home: const AgriMindScaffold(
        title: 'AGRIMIND',
        body: AgriMindErrorState(
          title: 'Configuration indisponible',
          message: 'La configuration publique de l’application est invalide.',
        ),
      ),
    );
  }
}
