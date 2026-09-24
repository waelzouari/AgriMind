import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/irrigation/domain/command_acknowledgement.dart';
import 'package:agrimind/features/irrigation/domain/pump_command.dart';

sealed class IrrigationRepositoryEvent {
  const IrrigationRepositoryEvent();
}

final class IrrigationConnectionChanged extends IrrigationRepositoryEvent {
  const IrrigationConnectionChanged(this.phase);
  final MqttConnectionPhase phase;
}

final class IrrigationAcknowledgementReceived
    extends IrrigationRepositoryEvent {
  const IrrigationAcknowledgementReceived(this.acknowledgement);
  final CommandAcknowledgement acknowledgement;
}

abstract interface class ManualIrrigationRepository {
  Stream<IrrigationRepositoryEvent> get events;
  Future<void> connect({required String farmId, required String deviceId});
  Future<bool> publish(PumpCommand command);
  Future<void> disconnect();
}
