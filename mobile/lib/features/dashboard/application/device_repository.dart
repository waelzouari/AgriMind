import 'package:agrimind/features/dashboard/domain/device.dart';

abstract interface class DeviceRepository {
  Future<Device> findActiveDevice(String farmId);
}

final class DeviceResolutionException implements Exception {
  const DeviceResolutionException(this.message);
  final String message;
}
