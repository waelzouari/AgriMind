import 'dart:async';

import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_repository.dart';
import 'package:agrimind/features/irrigation/domain/command_acknowledgement.dart';
import 'package:agrimind/features/irrigation/domain/pump_command.dart';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';

enum ManualIrrigationPhase {
  idle,
  publishing,
  awaitingAcknowledgement,
  accepted,
  rejected,
  completed,
  failed,
  timedOut,
}

typedef IrrigationClock = DateTime Function();
typedef CommandIdFactory = String Function();
typedef TimeoutScheduler =
    Timer Function(Duration duration, void Function() callback);

final class ManualIrrigationController extends ChangeNotifier {
  ManualIrrigationController({
    required this._repository,
    required this._acknowledgementTimeout,
    required this._completionGrace,
    IrrigationClock? clock,
    CommandIdFactory? commandIdFactory,
    TimeoutScheduler? timeoutScheduler,
  }) : _clock = clock ?? DateTime.now,
       _commandIdFactory = commandIdFactory ?? const Uuid().v4,
       _timeoutScheduler =
           timeoutScheduler ??
           ((duration, callback) => Timer(duration, callback));

  final ManualIrrigationRepository _repository;
  final Duration _acknowledgementTimeout;
  final Duration _completionGrace;
  final IrrigationClock _clock;
  final CommandIdFactory _commandIdFactory;
  final TimeoutScheduler _timeoutScheduler;
  StreamSubscription<IrrigationRepositoryEvent>? _subscription;
  Timer? _timeout;
  String? _farmId;
  String? _deviceId;
  String? _requestedBy;
  PumpCommand? _command;
  CommandAcknowledgement? _acknowledgement;
  final Set<String> _seenAcknowledgements = {};
  MqttConnectionPhase _connectionPhase = MqttConnectionPhase.idle;
  ManualIrrigationPhase _phase = ManualIrrigationPhase.idle;
  bool _disposed = false;

  MqttConnectionPhase get connectionPhase => _connectionPhase;
  ManualIrrigationPhase get phase => _phase;
  PumpCommand? get command => _command;
  CommandAcknowledgement? get acknowledgement => _acknowledgement;
  bool get canSubmit =>
      _connectionPhase == MqttConnectionPhase.connected && !isPending;
  bool get isPending => switch (_phase) {
    ManualIrrigationPhase.publishing ||
    ManualIrrigationPhase.awaitingAcknowledgement ||
    ManualIrrigationPhase.accepted => true,
    _ => false,
  };

  Future<void> start({
    required String farmId,
    required String deviceId,
    required String requestedBy,
  }) async {
    await stop();
    _farmId = farmId;
    _deviceId = deviceId;
    _requestedBy = requestedBy;
    _connectionPhase = MqttConnectionPhase.connecting;
    notifyListeners();
    _subscription = _repository.events.listen(_onEvent);
    await _repository.connect(farmId: farmId, deviceId: deviceId);
  }

  Future<bool> submit(int durationSeconds) async {
    if (!canSubmit || durationSeconds < 1 || durationSeconds > 600) {
      return false;
    }
    final now = _clock().toUtc();
    final command = PumpCommand(
      commandId: _commandIdFactory(),
      farmId: _farmId!,
      deviceId: _deviceId!,
      durationSeconds: durationSeconds,
      issuedAt: now,
      expiresAt: now.add(_acknowledgementTimeout),
      requestedBy: _requestedBy!,
    );
    _command = command;
    _acknowledgement = null;
    _seenAcknowledgements.clear();
    _phase = ManualIrrigationPhase.publishing;
    notifyListeners();
    final brokerConfirmed = await _repository.publish(command);
    if (_disposed || _command?.commandId != command.commandId) return false;
    if (!brokerConfirmed) {
      _phase = ManualIrrigationPhase.failed;
      notifyListeners();
      return false;
    }
    _phase = ManualIrrigationPhase.awaitingAcknowledgement;
    _scheduleTimeout(_acknowledgementTimeout);
    notifyListeners();
    return true;
  }

  void _onEvent(IrrigationRepositoryEvent event) {
    switch (event) {
      case IrrigationConnectionChanged(:final phase):
        _connectionPhase = phase;
      case IrrigationAcknowledgementReceived(:final acknowledgement):
        _applyAcknowledgement(acknowledgement);
    }
    notifyListeners();
  }

  void _applyAcknowledgement(CommandAcknowledgement value) {
    final command = _command;
    if (command == null ||
        value.commandId != command.commandId ||
        value.farmId != command.farmId ||
        value.deviceId != command.deviceId ||
        !_seenAcknowledgements.add(value.acknowledgementId)) {
      return;
    }
    switch (value.status) {
      case CommandAcknowledgementStatus.accepted:
        if (_phase != ManualIrrigationPhase.awaitingAcknowledgement) return;
        _acknowledgement = value;
        _phase = ManualIrrigationPhase.accepted;
        _scheduleTimeout(
          Duration(seconds: command.durationSeconds) + _completionGrace,
        );
      case CommandAcknowledgementStatus.rejected:
        if (_phase != ManualIrrigationPhase.awaitingAcknowledgement) return;
        _terminal(value, ManualIrrigationPhase.rejected);
      case CommandAcknowledgementStatus.completed:
        if (_phase != ManualIrrigationPhase.accepted) return;
        _terminal(value, ManualIrrigationPhase.completed);
      case CommandAcknowledgementStatus.failed:
        if (_phase != ManualIrrigationPhase.awaitingAcknowledgement &&
            _phase != ManualIrrigationPhase.accepted) {
          return;
        }
        _terminal(value, ManualIrrigationPhase.failed);
    }
  }

  void _terminal(CommandAcknowledgement value, ManualIrrigationPhase phase) {
    _timeout?.cancel();
    _timeout = null;
    _acknowledgement = value;
    _phase = phase;
  }

  void _scheduleTimeout(Duration duration) {
    _timeout?.cancel();
    final commandId = _command?.commandId;
    _timeout = _timeoutScheduler(duration, () {
      if (_command?.commandId == commandId && isPending) {
        _phase = ManualIrrigationPhase.timedOut;
        notifyListeners();
      }
    });
  }

  void resetResult() {
    if (isPending) return;
    _command = null;
    _acknowledgement = null;
    _seenAcknowledgements.clear();
    _phase = ManualIrrigationPhase.idle;
    notifyListeners();
  }

  Future<void> stop() async {
    _timeout?.cancel();
    _timeout = null;
    await _subscription?.cancel();
    _subscription = null;
    await _repository.disconnect();
    _farmId = null;
    _deviceId = null;
    _requestedBy = null;
    _command = null;
    _acknowledgement = null;
    _seenAcknowledgements.clear();
    _connectionPhase = MqttConnectionPhase.idle;
    _phase = ManualIrrigationPhase.idle;
  }

  @override
  void dispose() {
    _disposed = true;
    _timeout?.cancel();
    unawaited(_subscription?.cancel());
    unawaited(_repository.disconnect());
    super.dispose();
  }
}
