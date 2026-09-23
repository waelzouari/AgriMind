final class AppConfig {
  const AppConfig({
    this.appName = 'AGRIMIND',
    required this.supabaseUrl,
    required this.supabaseAnonKey,
  });

  factory AppConfig.fromEnvironment() => const AppConfig(
    supabaseUrl: String.fromEnvironment('AGRIMIND_SUPABASE_URL'),
    supabaseAnonKey: String.fromEnvironment('AGRIMIND_SUPABASE_ANON_KEY'),
  );

  final String appName;
  final String supabaseUrl;
  final String supabaseAnonKey;

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
  }
}
