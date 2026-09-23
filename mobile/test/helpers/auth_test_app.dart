import 'package:agrimind/app/agrimind_app.dart';
import 'package:agrimind/core/config/app_config.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:flutter/widgets.dart';

import 'fake_farm_repository.dart';

const testConfig = AppConfig(
  supabaseUrl: 'https://project-ref.supabase.co',
  supabaseAnonKey: 'public-anon-placeholder',
);

Widget authTestApp(
  AuthenticationController controller, {
  FakeFarmRepository? farmRepository,
}) {
  final repository =
      farmRepository ??
      FakeFarmRepository(
        currentFarm: const Farm(id: 'farm-a', name: 'Ferme A'),
      );
  return AgriMindApp(
    config: testConfig,
    authentication: controller,
    farmController: FarmController(repository),
  );
}
