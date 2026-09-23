import 'package:agrimind/features/dashboard/domain/telemetry_reading.dart';

enum MqttConnectionPhase {
  idle,
  connecting,
  connected,
  reconnecting,
  disconnected,
  failure,
}

sealed class TelemetryEvent {
  const TelemetryEvent();
}

final class TelemetryConnectionChanged extends TelemetryEvent {
  const TelemetryConnectionChanged(this.phase);
  final MqttConnectionPhase phase;
}

final class TelemetryReceived extends TelemetryEvent {
  const TelemetryReceived(this.reading);
  final TelemetryReading reading;
}

abstract interface class TelemetryRepository {
  Stream<TelemetryEvent> get events;
  Future<void> connect({required String farmId, required String deviceId});
  Future<void> disconnect();
}
