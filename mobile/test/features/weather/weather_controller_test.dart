import 'dart:async';

import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/weather/application/weather_controller.dart';
import 'package:agrimind/features/weather/domain/weather_failure.dart';
import 'package:agrimind/features/weather/domain/weather_snapshot.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_weather_repository.dart';
import 'weather_test_data.dart';

final farm = Farm(
  id: 'farm-a',
  name: 'Ferme A',
  latitude: 34.74,
  longitude: 10.76,
);

final class _FakeSchedule implements WeatherSchedule {
  _FakeSchedule(this.callback);
  final void Function() callback;
  bool cancelled = false;
  @override
  void cancel() => cancelled = true;
  void fire() {
    if (!cancelled) callback();
  }
}

void main() {
  test('exposes loading until the initial request completes', () async {
    final request = Completer<WeatherSnapshot?>();
    final repository = FakeWeatherRepository()..completer = request;
    final controller = WeatherController(repository: repository);
    final load = controller.load(farm);
    expect(controller.status, WeatherStatus.loading);
    expect(controller.isRefreshing, isTrue);
    request.complete(null);
    await load;
    controller.dispose();
  });

  test('does not query weather when farm location is missing', () async {
    final repository = FakeWeatherRepository();
    final controller = WeatherController(repository: repository);

    await controller.load(Farm(id: 'farm-a', name: 'Ferme A'));

    expect(controller.status, WeatherStatus.locationNotConfigured);
    expect(repository.calls, 0);
    controller.dispose();
  });

  test('exposes no-snapshot distinctly from a failure', () async {
    final controller = WeatherController(repository: FakeWeatherRepository());
    await controller.load(farm);
    expect(controller.status, WeatherStatus.noSnapshot);
    expect(controller.failure, isNull);
    controller.dispose();
  });

  test(
    'classifies fresh, stale, and expired snapshots at initial load',
    () async {
      final cases = {
        DateTime.parse('2026-09-24T10:10:00Z'): WeatherStatus.ready,
        DateTime.parse('2026-09-24T10:30:00Z'): WeatherStatus.ready,
        DateTime.parse('2026-09-24T11:00:00.001Z'): WeatherStatus.unavailable,
      };
      for (final entry in cases.entries) {
        final repository = FakeWeatherRepository()..result = weatherSnapshot();
        final controller = WeatherController(
          repository: repository,
          clock: () => entry.key,
        );
        await controller.load(farm);
        expect(controller.status, entry.value);
        controller.dispose();
      }
    },
  );

  test('reports a network failure without pretending it is stale', () async {
    final repository = FakeWeatherRepository()
      ..error = const WeatherFailure(WeatherFailureType.network);
    final controller = WeatherController(repository: repository);
    await controller.load(farm);
    expect(controller.status, WeatherStatus.failure);
    expect(controller.isOffline, isTrue);
    expect(controller.freshness, isNull);
    controller.dispose();
  });

  test('keeps usable cached data with a separate offline warning', () async {
    final now = DateTime.parse('2026-09-24T10:10:00Z');
    final repository = FakeWeatherRepository()..result = weatherSnapshot();
    final controller = WeatherController(
      repository: repository,
      clock: () => now,
    );
    await controller.load(farm);
    repository.error = const WeatherFailure(WeatherFailureType.network);

    await controller.refresh();

    expect(controller.status, WeatherStatus.ready);
    expect(controller.snapshot, isNotNull);
    expect(controller.freshness, WeatherFreshness.fresh);
    expect(controller.isOffline, isTrue);
    controller.dispose();
  });

  test('keeps stale cached data with a separate offline warning', () async {
    final repository = FakeWeatherRepository()..result = weatherSnapshot();
    final controller = WeatherController(
      repository: repository,
      clock: () => DateTime.parse('2026-09-24T10:30:00Z'),
    );
    await controller.load(farm);
    repository.error = const WeatherFailure(WeatherFailureType.network);
    await controller.refresh();
    expect(controller.status, WeatherStatus.ready);
    expect(controller.freshness, WeatherFreshness.stale);
    expect(controller.isOffline, isTrue);
    controller.dispose();
  });

  test(
    'a successful refresh replaces the snapshot and clears warnings',
    () async {
      final repository = FakeWeatherRepository()..result = weatherSnapshot();
      final controller = WeatherController(
        repository: repository,
        clock: () => DateTime.parse('2026-09-24T10:10:00Z'),
      );
      await controller.load(farm);
      repository.error = const WeatherFailure(WeatherFailureType.network);
      await controller.refresh();
      final replacement = weatherSnapshot(
        freshUntil: '2026-09-24T10:20:00Z',
        staleUntil: '2026-09-24T12:00:00Z',
      );
      repository
        ..error = null
        ..result = replacement;
      await controller.refresh();
      expect(controller.snapshot, same(replacement));
      expect(controller.isOffline, isFalse);
      expect(controller.failure, isNull);
      controller.dispose();
    },
  );

  test('masks expired data when an offline refresh fails', () async {
    var now = DateTime.parse('2026-09-24T10:10:00Z');
    final repository = FakeWeatherRepository()..result = weatherSnapshot();
    final controller = WeatherController(
      repository: repository,
      clock: () => now,
    );
    await controller.load(farm);
    now = DateTime.parse('2026-09-24T11:00:00.001Z');
    repository.error = const WeatherFailure(WeatherFailureType.network);

    await controller.refresh();

    expect(controller.status, WeatherStatus.unavailable);
    expect(controller.snapshot, isNull);
    expect(controller.isOffline, isTrue);
    controller.dispose();
  });

  test('unauthorized failure clears cached weather', () async {
    final repository = FakeWeatherRepository()..result = weatherSnapshot();
    final controller = WeatherController(
      repository: repository,
      clock: () => DateTime.parse('2026-09-24T10:10:00Z'),
    );
    await controller.load(farm);
    repository.error = const WeatherFailure(WeatherFailureType.unauthorized);

    await controller.refresh();

    expect(controller.status, WeatherStatus.failure);
    expect(controller.snapshot, isNull);
    expect(controller.failure?.type, WeatherFailureType.unauthorized);
    controller.dispose();
  });

  test(
    'one-shot timers move fresh to stale to unavailable without fetching',
    () async {
      var now = DateTime.parse('2026-09-24T10:10:00Z');
      final schedules = <_FakeSchedule>[];
      final repository = FakeWeatherRepository()..result = weatherSnapshot();
      final controller = WeatherController(
        repository: repository,
        clock: () => now,
        schedule: (delay, callback) {
          expect(delay, greaterThan(Duration.zero));
          final schedule = _FakeSchedule(callback);
          schedules.add(schedule);
          return schedule;
        },
      );
      await controller.load(farm);
      expect(controller.freshness, WeatherFreshness.fresh);
      expect(
        schedules.length,
        1,
        reason: 'Only one future boundary may be scheduled at a time.',
      );

      now = DateTime.parse('2026-09-24T10:15:00.001Z');
      schedules.last.fire();
      expect(controller.freshness, WeatherFreshness.stale);

      now = DateTime.parse('2026-09-24T11:00:00.001Z');
      schedules.last.fire();
      expect(controller.status, WeatherStatus.unavailable);
      expect(repository.calls, 1);
      controller.dispose();
    },
  );

  test('new snapshots replace the timer and dispose cancels it', () async {
    final schedules = <_FakeSchedule>[];
    final repository = FakeWeatherRepository()..result = weatherSnapshot();
    final controller = WeatherController(
      repository: repository,
      clock: () => DateTime.parse('2026-09-24T10:10:00Z'),
      schedule: (delay, callback) {
        final result = _FakeSchedule(callback);
        schedules.add(result);
        return result;
      },
    );
    await controller.load(farm);
    final first = schedules.single;
    repository.result = weatherSnapshot(
      freshUntil: '2026-09-24T10:30:00Z',
      staleUntil: '2026-09-24T12:00:00Z',
    );
    await controller.refresh();
    expect(first.cancelled, isTrue);
    expect(schedules.last.cancelled, isFalse);
    controller.dispose();
    expect(schedules.last.cancelled, isTrue);
    expect(schedules.last.callback, returnsNormally);
  });

  test('ignores an obsolete response after the farm changes', () async {
    final oldRequest = Completer<WeatherSnapshot?>();
    final repository = FakeWeatherRepository()..completer = oldRequest;
    final controller = WeatherController(repository: repository);
    final first = controller.load(farm);
    repository.completer = null;
    repository.result = null;
    final newFarm = Farm(
      id: 'farm-b',
      name: 'Ferme B',
      latitude: 35,
      longitude: 10,
    );

    await controller.load(newFarm);
    oldRequest.complete(weatherSnapshot());
    await first;

    expect(controller.status, WeatherStatus.noSnapshot);
    expect(controller.snapshot, isNull);
    controller.dispose();
  });

  test('prevents concurrent manual refreshes', () async {
    final request = Completer<WeatherSnapshot?>();
    final repository = FakeWeatherRepository()..completer = request;
    final controller = WeatherController(repository: repository);
    final first = controller.load(farm);

    await controller.refresh();
    expect(repository.calls, 1);
    request.complete(null);
    await first;
    controller.dispose();
  });
}
