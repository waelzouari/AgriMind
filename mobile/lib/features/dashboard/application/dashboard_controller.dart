import 'dart:async';

import 'package:agrimind/features/dashboard/application/device_repository.dart';
import 'package:agrimind/features/dashboard/application/telemetry_repository.dart';
import 'package:agrimind/features/dashboard/domain/device.dart';
import 'package:agrimind/features/dashboard/domain/telemetry_reading.dart';
import 'package:agrimind/features/irrigation/application/manual_irrigation_controller.dart';
import 'package:flutter/foundation.dart';

typedef Clock = DateTime Function();

final class DashboardController extends ChangeNotifier {
  // Named dependencies keep composition sites self-documenting.
  // ignore: prefer_initializing_formals
  DashboardController({
    required this._deviceRepository,
    required this._telemetryRepository,
    required this._staleAfter,
    required this.manualIrrigation,
    Clock? clock,
    bool startFreshnessTimer = true,
  }) : _clock = clock ?? DateTime.now,
       // ignore: prefer_initializing_formals
       _startFreshnessTimer = startFreshnessTimer;

  final DeviceRepository _deviceRepository;
  final TelemetryRepository _telemetryRepository;
  final Duration _staleAfter;
  final ManualIrrigationController manualIrrigation;
  final Clock _clock;
  final bool _startFreshnessTimer;
  final Map<TelemetryMetric, TelemetryReading> _readings = {};
  final Set<String> _seenMessageIds = {};
  final List<String> _messageIdOrder = [];
  StreamSubscription<TelemetryEvent>? _subscription;
  Timer? _freshnessTimer;
  Device? _device;
  String? _farmId;
  String? _requestedBy;
  MqttConnectionPhase _phase = MqttConnectionPhase.idle;
  String? _errorMessage;
  bool _disposed = false;

  MqttConnectionPhase get phase => _phase;
  Device? get device => _device;
  String? get errorMessage => _errorMessage;
  Map<TelemetryMetric, TelemetryReading> get readings =>
      Map.unmodifiable(_readings);
  DateTime? get lastTelemetryAt => _readings.values.isEmpty
      ? null
      : _readings.values
            .map((r) => r.recordedAt)
            .reduce((a, b) => a.isAfter(b) ? a : b);

  bool isStale(TelemetryReading reading) =>
      _clock().toUtc().difference(reading.recordedAt).compareTo(_staleAfter) >
      0;

  Future<void> start(String farmId, {required String requestedBy}) async {
    await stop();
    _farmId = farmId;
    _requestedBy = requestedBy;
    _phase = MqttConnectionPhase.connecting;
    _errorMessage = null;
    notifyListeners();
    try {
      final device = await _deviceRepository.findActiveDevice(farmId);
      if (_disposed) return;
      _device = device;
      _subscription = _telemetryRepository.events.listen(_onEvent);
      await manualIrrigation.start(
        farmId: farmId,
        deviceId: device.id,
        requestedBy: requestedBy,
      );
      if (_startFreshnessTimer) {
        _freshnessTimer = Timer.periodic(
          const Duration(seconds: 1),
          (_) => refreshFreshness(),
        );
      }
      await _telemetryRepository.connect(farmId: farmId, deviceId: device.id);
    } on DeviceResolutionException catch (error) {
      _phase = MqttConnectionPhase.failure;
      _errorMessage = error.message;
      notifyListeners();
    } on Object {
      _phase = MqttConnectionPhase.failure;
      _errorMessage = 'Les mesures en direct sont momentanément indisponibles.';
      notifyListeners();
    }
  }

  void _onEvent(TelemetryEvent event) {
    switch (event) {
      case TelemetryConnectionChanged(:final phase):
        _phase = phase;
        if (phase == MqttConnectionPhase.failure) {
          _errorMessage = 'La connexion MQTT est indisponible.';
        }
      case TelemetryReceived(:final reading):
        if (_seenMessageIds.contains(reading.messageId)) return;
        final current = _readings[reading.metric];
        if (current != null &&
            (reading.recordedAt.isBefore(current.recordedAt) ||
                (reading.recordedAt == current.recordedAt &&
                    reading.messageId.compareTo(current.messageId) <= 0))) {
          return;
        }
        _seenMessageIds.add(reading.messageId);
        _messageIdOrder.add(reading.messageId);
        if (_messageIdOrder.length > 256) {
          _seenMessageIds.remove(_messageIdOrder.removeAt(0));
        }
        _readings[reading.metric] = reading;
    }
    notifyListeners();
  }

  void refreshFreshness() {
    if (_readings.isNotEmpty) notifyListeners();
  }

  Future<void> retry() async {
    final farmId = _farmId;
    final requestedBy = _requestedBy;
    if (farmId == null || requestedBy == null) return;
    await start(farmId, requestedBy: requestedBy);
  }

  Future<void> stop() async {
    _freshnessTimer?.cancel();
    _freshnessTimer = null;
    await _subscription?.cancel();
    _subscription = null;
    await _telemetryRepository.disconnect();
    await manualIrrigation.stop();
    _readings.clear();
    _seenMessageIds.clear();
    _messageIdOrder.clear();
    _device = null;
    _farmId = null;
    _requestedBy = null;
    _phase = MqttConnectionPhase.idle;
    _errorMessage = null;
  }

  @override
  void dispose() {
    _disposed = true;
    _freshnessTimer?.cancel();
    unawaited(_subscription?.cancel());
    unawaited(_telemetryRepository.disconnect());
    manualIrrigation.dispose();
    super.dispose();
  }
}
