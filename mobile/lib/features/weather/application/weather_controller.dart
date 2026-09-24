import 'dart:async';

import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/weather/application/weather_repository.dart';
import 'package:agrimind/features/weather/domain/weather_failure.dart';
import 'package:agrimind/features/weather/domain/weather_snapshot.dart';
import 'package:flutter/foundation.dart';

typedef WeatherClock = DateTime Function();
typedef WeatherScheduleFactory =
    WeatherSchedule Function(Duration delay, VoidCallback callback);

abstract interface class WeatherSchedule {
  void cancel();
}

final class DartWeatherSchedule implements WeatherSchedule {
  DartWeatherSchedule(Duration delay, VoidCallback callback)
    : _timer = Timer(delay, callback);

  final Timer _timer;

  @override
  void cancel() => _timer.cancel();
}

enum WeatherStatus {
  idle,
  loading,
  ready,
  noSnapshot,
  locationNotConfigured,
  unavailable,
  failure,
}

final class WeatherController extends ChangeNotifier {
  WeatherController({
    required this.repository,
    WeatherClock? clock,
    WeatherScheduleFactory? schedule,
  }) : _clock = clock ?? DateTime.now,
       _schedule = schedule ?? DartWeatherSchedule.new;

  final WeatherRepository repository;
  final WeatherClock _clock;
  final WeatherScheduleFactory _schedule;

  WeatherStatus _status = WeatherStatus.idle;
  WeatherSnapshot? _cachedSnapshot;
  WeatherFreshness? _freshness;
  WeatherFailure? _failure;
  Farm? _farm;
  WeatherSchedule? _transition;
  int _generation = 0;
  bool _requestInProgress = false;
  bool _offline = false;
  bool _disposed = false;

  WeatherStatus get status => _status;
  WeatherSnapshot? get snapshot =>
      _status == WeatherStatus.ready ? _cachedSnapshot : null;
  WeatherFreshness? get freshness => _freshness;
  WeatherFailure? get failure => _failure;
  bool get isOffline => _offline;
  bool get isRefreshing => _requestInProgress;

  Future<void> load(Farm farm) async {
    _farm = farm;
    final generation = ++_generation;
    _cancelTransition();
    if (!farm.hasLocation) {
      _cachedSnapshot = null;
      _freshness = null;
      _failure = null;
      _offline = false;
      _requestInProgress = false;
      _setStatus(WeatherStatus.locationNotConfigured);
      return;
    }
    _requestInProgress = true;
    _failure = null;
    _offline = false;
    _setStatus(WeatherStatus.loading);
    await _fetch(farm, generation);
  }

  Future<void> refresh() async {
    final farm = _farm;
    if (farm == null || !farm.hasLocation || _requestInProgress) return;
    final generation = ++_generation;
    _requestInProgress = true;
    _failure = null;
    _notify();
    await _fetch(farm, generation);
  }

  Future<void> _fetch(Farm farm, int generation) async {
    try {
      final result = await repository.findForFarm(farm.id);
      if (!_isCurrent(generation)) return;
      _requestInProgress = false;
      _offline = false;
      _failure = null;
      if (result == null) {
        _cachedSnapshot = null;
        _freshness = null;
        _cancelTransition();
        _setStatus(WeatherStatus.noSnapshot);
        return;
      }
      _cachedSnapshot = result;
      _applyFreshness();
    } on WeatherFailure catch (failure) {
      if (!_isCurrent(generation)) return;
      _requestInProgress = false;
      _handleFailure(failure);
    } on Object {
      if (!_isCurrent(generation)) return;
      _requestInProgress = false;
      _handleFailure(const WeatherFailure(WeatherFailureType.unknown));
    }
  }

  void _handleFailure(WeatherFailure failure) {
    _failure = failure;
    if (failure.type == WeatherFailureType.unauthorized ||
        failure.type == WeatherFailureType.invalidSnapshot) {
      _cachedSnapshot = null;
      _freshness = null;
      _offline = false;
      _cancelTransition();
      _setStatus(WeatherStatus.failure);
      return;
    }
    final cachedFreshness = _cachedSnapshot?.freshnessAt(_clock());
    if (cachedFreshness != null &&
        cachedFreshness != WeatherFreshness.unavailable) {
      _freshness = cachedFreshness;
      _offline = failure.type == WeatherFailureType.network;
      _setStatus(WeatherStatus.ready);
      _scheduleTransition();
      return;
    }
    _freshness = cachedFreshness;
    _offline = failure.type == WeatherFailureType.network;
    _cancelTransition();
    _setStatus(
      cachedFreshness == WeatherFreshness.unavailable
          ? WeatherStatus.unavailable
          : WeatherStatus.failure,
    );
  }

  void _applyFreshness() {
    _freshness = _cachedSnapshot!.freshnessAt(_clock());
    _setStatus(
      _freshness == WeatherFreshness.unavailable
          ? WeatherStatus.unavailable
          : WeatherStatus.ready,
    );
    _scheduleTransition();
  }

  void _scheduleTransition() {
    _cancelTransition();
    final snapshot = _cachedSnapshot;
    if (snapshot == null || _status != WeatherStatus.ready) return;
    final now = _clock().toUtc();
    final boundary = _freshness == WeatherFreshness.fresh
        ? snapshot.freshUntil
        : snapshot.staleUntil;
    var delay = boundary.difference(now) + const Duration(microseconds: 1);
    if (delay <= Duration.zero) delay = const Duration(microseconds: 1);
    _transition = _schedule(delay, _onTransition);
  }

  void _onTransition() {
    if (_disposed || _cachedSnapshot == null) return;
    _freshness = _cachedSnapshot!.freshnessAt(_clock());
    if (_freshness == WeatherFreshness.unavailable) {
      _status = WeatherStatus.unavailable;
      _cancelTransition();
    } else {
      _scheduleTransition();
    }
    _notify();
  }

  bool _isCurrent(int generation) => !_disposed && generation == _generation;

  void _setStatus(WeatherStatus value) {
    _status = value;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void _cancelTransition() {
    _transition?.cancel();
    _transition = null;
  }

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    _cancelTransition();
    super.dispose();
  }
}
