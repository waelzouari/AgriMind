import 'package:agrimind/core/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('accepts public Supabase client configuration', () {
    const config = AppConfig(
      supabaseUrl: 'https://project-ref.supabase.co',
      supabaseAnonKey: 'public-client-key',
    );

    expect(config.validate, returnsNormally);
  });

  test('rejects missing, insecure, and privileged configuration', () {
    const invalidConfigs = [
      AppConfig(supabaseUrl: '', supabaseAnonKey: 'public-client-key'),
      AppConfig(
        supabaseUrl: 'http://project-ref.supabase.co',
        supabaseAnonKey: 'public-client-key',
      ),
      AppConfig(
        supabaseUrl: 'https://project-ref.supabase.co',
        supabaseAnonKey: '',
      ),
      AppConfig(
        supabaseUrl: 'https://project-ref.supabase.co',
        supabaseAnonKey: 'service_role-placeholder',
      ),
      AppConfig(
        supabaseUrl: 'https://project-ref.supabase.co',
        supabaseAnonKey: 'sb_secret_placeholder',
      ),
    ];

    for (final config in invalidConfigs) {
      expect(config.validate, throwsFormatException);
    }
  });
}
