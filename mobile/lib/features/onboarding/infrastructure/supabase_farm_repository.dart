import 'package:agrimind/features/onboarding/application/farm_repository.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/onboarding/domain/farm_failure.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

final class SupabaseFarmRepository implements FarmRepository {
  SupabaseFarmRepository(this._client);

  final SupabaseClient _client;

  @override
  Future<Farm?> findCurrentFarm() async {
    try {
      final row = await _client
          .from('farms')
          .select('id,name')
          .order('created_at')
          .limit(1)
          .maybeSingle();
      return row == null ? null : _mapFarm(row);
    } on PostgrestException catch (error) {
      throw mapFarmPostgrestException(error);
    } on Object {
      throw const FarmFailure(FarmFailureType.unavailable);
    }
  }

  @override
  Future<Farm> createCurrentUserFarm({required String name}) async {
    try {
      final row = await _client
          .rpc('create_farm_for_current_user', params: {'farm_name': name})
          .single();
      return _mapFarm(row);
    } on PostgrestException catch (error) {
      throw mapFarmPostgrestException(error);
    } on Object {
      throw const FarmFailure(FarmFailureType.unavailable);
    }
  }

  Farm _mapFarm(Map<String, dynamic> row) =>
      Farm(id: row['id'] as String, name: row['name'] as String);
}

FarmFailure mapFarmPostgrestException(PostgrestException error) {
  if (error.code == '42501') {
    return const FarmFailure(FarmFailureType.unauthorized);
  }
  if (error.code == '23505') {
    return const FarmFailure(FarmFailureType.conflict);
  }
  final code = error.code ?? '';
  if (code.startsWith('08') || code.startsWith('PGRST0')) {
    return const FarmFailure(FarmFailureType.unavailable);
  }
  return const FarmFailure(FarmFailureType.unknown);
}
