import 'package:agrimind/core/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

const validConfig = AppConfig(
  supabaseUrl: 'https://project-ref.supabase.co',
  supabaseAnonKey: 'public-client-key',
  mqttHost: 'mqtt.example.com',
  telemetryMqttUsername: 'telemetry',
  telemetryMqttPassword: 'telemetry-password', // pragma: allowlist secret
  commandMqttUsername: 'command',
  commandMqttPassword: 'command-password', // pragma: allowlist secret
  ackMqttUsername: 'ack',
  ackMqttPassword: 'ack-password', // pragma: allowlist secret
);

void main() {
  test('accepts public Supabase and three scoped MQTT configurations', () {
    expect(validConfig.validate, returnsNormally);
  });

  test(
    'rejects missing, insecure, privileged, or incomplete configuration',
    () {
      final invalidConfigs = [
        _copy(supabaseUrl: ''),
        _copy(supabaseUrl: 'http://project-ref.supabase.co'),
        _copy(supabaseAnonKey: ''),
        _copy(supabaseAnonKey: 'service_role-placeholder'),
        _copy(supabaseAnonKey: 'sb_secret_placeholder'),
        _copy(commandMqttPassword: ''),
        _copy(ackMqttUsername: ''),
        _copy(commandMqttUsername: validConfig.telemetryMqttUsername),
        _copy(ackMqttPassword: validConfig.commandMqttPassword),
        _copy(commandAcknowledgementTimeoutSeconds: 1),
      ];
      for (final config in invalidConfigs) {
        expect(config.validate, throwsFormatException);
      }
    },
  );
}

AppConfig _copy({
  String? supabaseUrl,
  String? supabaseAnonKey,
  String? commandMqttPassword,
  String? commandMqttUsername,
  String? ackMqttUsername,
  String? ackMqttPassword,
  int? commandAcknowledgementTimeoutSeconds,
}) => AppConfig(
  supabaseUrl: supabaseUrl ?? validConfig.supabaseUrl,
  supabaseAnonKey: supabaseAnonKey ?? validConfig.supabaseAnonKey,
  mqttHost: validConfig.mqttHost,
  telemetryMqttUsername: validConfig.telemetryMqttUsername,
  telemetryMqttPassword: validConfig.telemetryMqttPassword,
  commandMqttUsername: commandMqttUsername ?? validConfig.commandMqttUsername,
  commandMqttPassword: commandMqttPassword ?? validConfig.commandMqttPassword,
  ackMqttUsername: ackMqttUsername ?? validConfig.ackMqttUsername,
  ackMqttPassword: ackMqttPassword ?? validConfig.ackMqttPassword,
  commandAcknowledgementTimeoutSeconds:
      commandAcknowledgementTimeoutSeconds ??
      validConfig.commandAcknowledgementTimeoutSeconds,
);
