final class AppConfig {
  const AppConfig({
    this.appName = 'AGRIMIND',
    required this.supabaseUrl,
    required this.supabaseAnonKey,
    this.mqttHost = '',
    this.mqttPort = 8883,
    this.mqttUsername = '',
    this.mqttPassword = '',
    this.telemetryStaleSeconds = 30,
  });

  factory AppConfig.fromEnvironment() => const AppConfig(
    supabaseUrl: String.fromEnvironment('AGRIMIND_SUPABASE_URL'),
    supabaseAnonKey: String.fromEnvironment('AGRIMIND_SUPABASE_ANON_KEY'),
    mqttHost: String.fromEnvironment('AGRIMIND_MOBILE_MQTT_HOST'),
    mqttPort: int.fromEnvironment(
      'AGRIMIND_MOBILE_MQTT_PORT',
      defaultValue: 8883,
    ),
    mqttUsername: String.fromEnvironment('AGRIMIND_MOBILE_MQTT_USERNAME'),
    mqttPassword: String.fromEnvironment('AGRIMIND_MOBILE_MQTT_PASSWORD'),
    telemetryStaleSeconds: int.fromEnvironment(
      'AGRIMIND_MOBILE_TELEMETRY_STALE_SECONDS',
      defaultValue: 30,
    ),
  );

  final String appName;
  final String supabaseUrl;
  final String supabaseAnonKey;
  final String mqttHost;
  final int mqttPort;
  final String mqttUsername;
  final String mqttPassword;
  final int telemetryStaleSeconds;

  void validate() {
    final uri = Uri.tryParse(supabaseUrl);
    if (uri == null || uri.scheme != 'https' || uri.host.isEmpty) {
      throw const FormatException('Supabase public URL is invalid');
    }
    final normalizedKey = supabaseAnonKey.trim().toLowerCase();
    if (normalizedKey.isEmpty ||
        normalizedKey.contains('service_role') ||
        normalizedKey.startsWith('sb_secret_')) {
      throw const FormatException('Supabase public client key is invalid');
    }
    if (mqttHost.trim().isEmpty || mqttHost.contains('://')) {
      throw const FormatException('MQTT host is invalid');
    }
    if (mqttPort != 8883 ||
        mqttUsername.trim().isEmpty ||
        mqttPassword.isEmpty) {
      throw const FormatException('MQTT TLS client configuration is invalid');
    }
    if (telemetryStaleSeconds < 5 || telemetryStaleSeconds > 3600) {
      throw const FormatException(
        'Telemetry freshness configuration is invalid',
      );
    }
  }
}
