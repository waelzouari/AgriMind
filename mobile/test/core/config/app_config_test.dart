import 'package:agrimind/core/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('accepts public Supabase client configuration', () {
    const config = AppConfig(
      supabaseUrl: 'https://project-ref.supabase.co',
      supabaseAnonKey: 'public-client-key',
      mqttHost: 'mqtt.example.com',
      mqttUsername: 'mobile-read-only',
      mqttPassword: 'test-password', // pragma: allowlist secret
    );

    expect(config.validate, returnsNormally);
  });

  test('rejects missing, insecure, and privileged configuration', () {
    const invalidConfigs = [
      AppConfig(
        supabaseUrl: '',
        supabaseAnonKey: 'public-client-key',
        mqttHost: 'mqtt.example.com',
        mqttUsername: 'u',
        mqttPassword: 'p', // pragma: allowlist secret
      ),
      AppConfig(
        supabaseUrl: 'http://project-ref.supabase.co',
        supabaseAnonKey: 'public-client-key',
        mqttHost: 'mqtt.example.com',
        mqttUsername: 'u',
        mqttPassword: 'p', // pragma: allowlist secret
      ),
      AppConfig(
        supabaseUrl: 'https://project-ref.supabase.co',
        supabaseAnonKey: '',
        mqttHost: 'mqtt.example.com',
        mqttUsername: 'u',
        mqttPassword: 'p', // pragma: allowlist secret
      ),
      AppConfig(
        supabaseUrl: 'https://project-ref.supabase.co',
        supabaseAnonKey: 'service_role-placeholder',
        mqttHost: 'mqtt.example.com',
        mqttUsername: 'u',
        mqttPassword: 'p', // pragma: allowlist secret
      ),
      AppConfig(
        supabaseUrl: 'https://project-ref.supabase.co',
        supabaseAnonKey: 'sb_secret_placeholder',
        mqttHost: 'mqtt.example.com',
        mqttUsername: 'u',
        mqttPassword: 'p', // pragma: allowlist secret
      ),
      AppConfig(
        supabaseUrl: 'https://project-ref.supabase.co',
        supabaseAnonKey: 'public-client-key',
      ),
    ];

    for (final config in invalidConfigs) {
      expect(config.validate, throwsFormatException);
    }
  });
}
