import 'dart:async';

import 'package:agrimind/features/irrigation/application/manual_irrigation_repository.dart';
import 'package:agrimind/features/irrigation/domain/pump_command.dart';

final class FakeManualIrrigationRepository
    implements ManualIrrigationRepository {
  final controller = StreamController<IrrigationRepositoryEvent>.broadcast();
  PumpCommand? publishedCommand;
  int publishCalls = 0;
  int disconnectCalls = 0;
  bool publishConfirmed = true;

  @override
  Stream<IrrigationRepositoryEvent> get events => controller.stream;
  @override
  Future<void> connect({
    required String farmId,
    required String deviceId,
  }) async {}
  @override
  Future<bool> publish(PumpCommand command) async {
    publishCalls++;
    publishedCommand = command;
    return publishConfirmed;
  }

  @override
  Future<void> disconnect() async => disconnectCalls++;
}
