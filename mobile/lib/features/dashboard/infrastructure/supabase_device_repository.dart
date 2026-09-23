import 'package:agrimind/features/dashboard/application/device_repository.dart';
import 'package:agrimind/features/dashboard/domain/device.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

final class SupabaseDeviceRepository implements DeviceRepository {
  SupabaseDeviceRepository(this._client);
  final SupabaseClient _client;

  @override
  Future<Device> findActiveDevice(String farmId) async {
    try {
      final rows = await _client
          .from('devices')
          .select('id,farm_id,label')
          .eq('farm_id', farmId)
          .eq('is_active', true)
          .order('created_at')
          .limit(2);
      if (rows.length != 1) {
        throw DeviceResolutionException(
          rows.isEmpty
              ? 'Aucun appareil actif n’est configuré pour cette ferme.'
              : 'Plusieurs appareils actifs sont configurés pour cette ferme.',
        );
      }
      final row = rows.single;
      return Device(
        id: row['id'] as String,
        farmId: row['farm_id'] as String,
        label: row['label'] as String?,
      );
    } on DeviceResolutionException {
      rethrow;
    } on Object {
      throw const DeviceResolutionException(
        'L’appareil de la ferme ne peut pas être chargé.',
      );
    }
  }
}
