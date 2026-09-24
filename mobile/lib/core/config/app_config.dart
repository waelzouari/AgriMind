final class AppConfig {
  const AppConfig({
    this.appName = 'AGRIMIND',
    required this.supabaseUrl,
    required this.supabaseAnonKey,
    this.mqttHost = '',
    this.mqttPort = 8883,
    this.telemetryMqttUsername = '',
    this.telemetryMqttPassword = '',
    this.commandMqttUsername = '',
    this.commandMqttPassword = '',
    this.ackMqttUsername = '',
    this.ackMqttPassword = '',
    this.telemetryStaleSeconds = 30,
    this.commandAcknowledgementTimeoutSeconds = 15,
    this.commandCompletionGraceSeconds = 30,
  });

  factory AppConfig.fromEnvironment() => const AppConfig(
    supabaseUrl: String.fromEnvironment('AGRIMIND_SUPABASE_URL'),
    supabaseAnonKey: String.fromEnvironment('AGRIMIND_SUPABASE_ANON_KEY'),
    mqttHost: String.fromEnvironment('AGRIMIND_MOBILE_MQTT_HOST'),
    mqttPort: int.fromEnvironment(
      'AGRIMIND_MOBILE_MQTT_PORT',
      defaultValue: 8883,
    ),
    telemetryMqttUsername: String.fromEnvironment(
      'AGRIMIND_MOBILE_MQTT_TELEMETRY_USERNAME',
    ),
    telemetryMqttPassword: String.fromEnvironment(
      'AGRIMIND_MOBILE_MQTT_TELEMETRY_PASSWORD',
    ),
    commandMqttUsername: String.fromEnvironment(
      'AGRIMIND_MOBILE_MQTT_COMMAND_USERNAME',
    ),
    commandMqttPassword: String.fromEnvironment(
      'AGRIMIND_MOBILE_MQTT_COMMAND_PASSWORD',
    ),
    ackMqttUsername: String.fromEnvironment(
      'AGRIMIND_MOBILE_MQTT_ACK_USERNAME',
    ),
    ackMqttPassword: String.fromEnvironment(
      'AGRIMIND_MOBILE_MQTT_ACK_PASSWORD',
    ),
    telemetryStaleSeconds: int.fromEnvironment(
      'AGRIMIND_MOBILE_TELEMETRY_STALE_SECONDS',
      defaultValue: 30,
    ),
    commandAcknowledgementTimeoutSeconds: int.fromEnvironment(
      'AGRIMIND_MOBILE_COMMAND_ACK_TIMEOUT_SECONDS',
      defaultValue: 15,
    ),
    commandCompletionGraceSeconds: int.fromEnvironment(
      'AGRIMIND_MOBILE_COMMAND_COMPLETION_GRACE_SECONDS',
      defaultValue: 30,
    ),
  );

  final String appName;
  final String supabaseUrl;
  final String supabaseAnonKey;
  final String mqttHost;
  final int mqttPort;
  final String telemetryMqttUsername;
  final String telemetryMqttPassword;
  final String commandMqttUsername;
  final String commandMqttPassword;
  final String ackMqttUsername;
  final String ackMqttPassword;
  final int telemetryStaleSeconds;
  final int commandAcknowledgementTimeoutSeconds;
  final int commandCompletionGraceSeconds;

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
        telemetryMqttUsername.trim().isEmpty ||
        telemetryMqttPassword.isEmpty ||
        commandMqttUsername.trim().isEmpty ||
        commandMqttPassword.isEmpty ||
        ackMqttUsername.trim().isEmpty ||
        ackMqttPassword.isEmpty) {
      throw const FormatException('MQTT TLS client configuration is invalid');
    }
    if ({telemetryMqttUsername, commandMqttUsername, ackMqttUsername}.length !=
        3) {
      throw const FormatException('MQTT client identities must be separate');
    }
    if ({telemetryMqttPassword, commandMqttPassword, ackMqttPassword}.length !=
        3) {
      throw const FormatException('MQTT client credentials must be separate');
    }
    if (telemetryStaleSeconds < 5 || telemetryStaleSeconds > 3600) {
      throw const FormatException(
        'Telemetry freshness configuration is invalid',
      );
    }
    if (commandAcknowledgementTimeoutSeconds < 5 ||
        commandAcknowledgementTimeoutSeconds > 120 ||
        commandCompletionGraceSeconds < 5 ||
        commandCompletionGraceSeconds > 300) {
      throw const FormatException(
        'MQTT command timeout configuration is invalid',
      );
    }
  }
}
