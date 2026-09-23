import 'package:agrimind/app/agrimind_app.dart';
import 'package:agrimind/core/config/app_config.dart';
import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/infrastructure/supabase_authentication_repository.dart';
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
    final repository = SupabaseAuthenticationRepository(
      Supabase.instance.client,
    );
    runApp(
      AgriMindApp(
        config: config,
        authentication: AuthenticationController(repository),
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
