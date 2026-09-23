import 'package:agrimind/features/onboarding/domain/farm.dart';

abstract interface class FarmRepository {
  Future<Farm?> findCurrentFarm();

  Future<Farm> createCurrentUserFarm({required String name});
}
