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
          .select('id,name,latitude,longitude')
          .order('created_at')
          .limit(1)
          .maybeSingle();
      return row == null ? null : mapFarmRow(row);
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
      return mapFarmRow(row);
    } on PostgrestException catch (error) {
      throw mapFarmPostgrestException(error);
    } on Object {
      throw const FarmFailure(FarmFailureType.unavailable);
    }
  }
}

Farm mapFarmRow(Map<String, dynamic> row) {
  final latitude = _optionalCoordinate(row['latitude'], 'latitude');
  final longitude = _optionalCoordinate(row['longitude'], 'longitude');
  if ((latitude == null) != (longitude == null)) {
    throw const FormatException('Farm coordinates must be paired.');
  }
  if (latitude != null && (latitude < -90 || latitude > 90)) {
    throw const FormatException('Farm latitude is out of range.');
  }
  if (longitude != null && (longitude < -180 || longitude > 180)) {
    throw const FormatException('Farm longitude is out of range.');
  }
  return Farm(
    id: row['id'] as String,
    name: row['name'] as String,
    latitude: latitude,
    longitude: longitude,
  );
}

double? _optionalCoordinate(Object? value, String field) {
  if (value == null) return null;
  if (value is! num) throw FormatException('$field must be numeric.');
  final coordinate = value.toDouble();
  if (!coordinate.isFinite) throw FormatException('$field must be finite.');
  return coordinate;
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
