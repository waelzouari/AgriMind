import 'package:agrimind/app/agrimind_app.dart';
import 'package:agrimind/core/config/app_config.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:flutter/widgets.dart';

const testConfig = AppConfig(
  supabaseUrl: 'https://project-ref.supabase.co',
  supabaseAnonKey: 'public-anon-placeholder',
);

Widget authTestApp(AuthenticationController controller) =>
    AgriMindApp(config: testConfig, authentication: controller);
