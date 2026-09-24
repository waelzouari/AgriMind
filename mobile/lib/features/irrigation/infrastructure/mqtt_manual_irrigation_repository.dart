// ignore_for_file: prefer_initializing_formals

import 'dart:async';

import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/dashboard/infrastructure/mqtt_wire_client.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_repository.dart';
import 'package:agrimind/features/irrigation/domain/command_acknowledgement.dart';
import 'package:agrimind/features/irrigation/domain/pump_command.dart';
import 'package:agrimind/features/irrigation/infrastructure/irrigation_topic.dart';
import 'package:agrimind/features/irrigation/infrastructure/mqtt_command_wire_client.dart';

final class MqttManualIrrigationRepository
    implements ManualIrrigationRepository {
  MqttManualIrrigationRepository({
    required MqttCommandWireClient commandClient,
    required MqttWireClient acknowledgementClient,
    // Public dependency names keep composition sites readable.
  }) : _commandClient = commandClient,
       _acknowledgementClient = acknowledgementClient;

  final MqttCommandWireClient _commandClient;
  final MqttWireClient _acknowledgementClient;
  final _events = StreamController<IrrigationRepositoryEvent>.broadcast();
  StreamSubscription<WireConnectionEvent>? _commandConnections;
  StreamSubscription<WireConnectionEvent>? _ackConnections;
  StreamSubscription<WireMessage>? _acknowledgements;
  IrrigationTopic? _topic;
  WireConnectionEvent? _commandPhase;
  WireConnectionEvent? _ackPhase;

  @override
  Stream<IrrigationRepositoryEvent> get events => _events.stream;

  @override
  Future<void> connect({
    required String farmId,
    required String deviceId,
  }) async {
    await disconnect();
    final topic = IrrigationTopic(farmId: farmId, deviceId: deviceId);
    _topic = topic;
    _events.add(
      const IrrigationConnectionChanged(MqttConnectionPhase.connecting),
    );
    _commandConnections = _commandClient.connectionEvents.listen((event) {
      _commandPhase = event;
      _emitCombinedPhase();
    });
    _ackConnections = _acknowledgementClient.connectionEvents.listen((event) {
      _ackPhase = event;
      _emitCombinedPhase();
    });
    _acknowledgements = _acknowledgementClient.messages.listen((message) {
      final commandId = topic.parseAcknowledgement(message.topic);
      if (commandId == null) return;
      final acknowledgement = CommandAcknowledgement.tryDecode(
        message.payload,
        topicCommandId: commandId,
        expectedFarmId: farmId,
        expectedDeviceId: deviceId,
      );
      if (acknowledgement != null) {
        _events.add(IrrigationAcknowledgementReceived(acknowledgement));
      }
    });
    await Future.wait([
      _acknowledgementClient.connect(topicFilter: topic.acknowledgementFilter),
      _commandClient.connect(),
    ]);
  }

  void _emitCombinedPhase() {
    final phases = {_commandPhase, _ackPhase};
    final phase = phases.contains(WireConnectionEvent.failure)
        ? MqttConnectionPhase.failure
        : phases.contains(WireConnectionEvent.reconnecting)
        ? MqttConnectionPhase.reconnecting
        : phases.contains(WireConnectionEvent.disconnected)
        ? MqttConnectionPhase.disconnected
        : _commandPhase == WireConnectionEvent.connected &&
              _ackPhase == WireConnectionEvent.connected
        ? MqttConnectionPhase.connected
        : MqttConnectionPhase.connecting;
    _events.add(IrrigationConnectionChanged(phase));
  }

  @override
  Future<bool> publish(PumpCommand command) async {
    final topic = _topic;
    if (topic == null ||
        command.farmId != topic.farmId ||
        command.deviceId != topic.deviceId) {
      return false;
    }
    return _commandClient.publish(
      topic: topic.command,
      payload: command.toJson(),
    );
  }

  @override
  Future<void> disconnect() async {
    await _commandConnections?.cancel();
    await _ackConnections?.cancel();
    await _acknowledgements?.cancel();
    _commandConnections = null;
    _ackConnections = null;
    _acknowledgements = null;
    _commandPhase = null;
    _ackPhase = null;
    _topic = null;
    await Future.wait([
      _commandClient.disconnect(),
      _acknowledgementClient.disconnect(),
    ]);
  }
}
