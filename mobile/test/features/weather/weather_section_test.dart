import 'dart:async';

import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/weather/application/weather_controller.dart';
import 'package:agrimind/features/weather/domain/weather_failure.dart';
import 'package:agrimind/features/weather/domain/weather_snapshot.dart';
import 'package:agrimind/features/weather/presentation/weather_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_weather_repository.dart';
import 'weather_test_data.dart';

final locatedFarm = Farm(
  id: 'farm-a',
  name: 'Ferme A',
  latitude: 34.74,
  longitude: 10.76,
);

Widget _app(WeatherController controller, {double textScale = 1}) =>
    MaterialApp(
      theme: AgriMindTheme.light,
      home: MediaQuery(
        data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
        child: Scaffold(
          body: SafeArea(
            child: SingleChildScrollView(
              child: WeatherSection(controller: controller),
            ),
          ),
        ),
      ),
    );

void main() {
  testWidgets('shows loading while the repository request is pending', (
    tester,
  ) async {
    final repository = FakeWeatherRepository()
      ..completer = Completer<WeatherSnapshot?>();
    final controller = WeatherController(repository: repository);
    controller.load(locatedFarm);
    await tester.pumpWidget(_app(controller));
    expect(find.text('Chargement météo'), findsOneWidget);
    controller.dispose();
  });

  testWidgets('renders only approved metrics with deterministic formatting', (
    tester,
  ) async {
    final repository = FakeWeatherRepository()..result = weatherSnapshot();
    final controller = WeatherController(
      repository: repository,
      clock: () => DateTime.parse('2026-09-24T10:10:00Z'),
    );
    await controller.load(locatedFarm);
    await tester.pumpWidget(_app(controller));
    expect(find.text('À jour'), findsOneWidget);
    for (final value in ['24.3', '64', '11.3', '0.3', '3.5', '2.4']) {
      expect(find.text(value), findsOneWidget);
    }
    expect(find.text('sur 15 min'), findsOneWidget);
    expect(find.textContaining('Pluie sur 6'), findsNothing);
    expect(find.textContaining('Pluie sur 12'), findsNothing);
    expect(find.textContaining('précédentes'), findsNothing);
    expect(find.textContaining('24/09/2026'), findsOneWidget);
    expect(
      find.bySemanticsLabel(RegExp('Température.*24.3.*°C')),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
    controller.dispose();
  });

  testWidgets('pads local date fields and handles a non-minute interval', (
    tester,
  ) async {
    final localFetchedAt = DateTime(2026, 2, 1, 3, 4);
    final row = weatherRow(
      fetchedAt: localFetchedAt.toUtc().toIso8601String(),
      freshUntil: localFetchedAt
          .add(const Duration(minutes: 15))
          .toUtc()
          .toIso8601String(),
      staleUntil: localFetchedAt
          .add(const Duration(hours: 1))
          .toUtc()
          .toIso8601String(),
    )..['current_interval_seconds'] = 61;
    final repository = FakeWeatherRepository()
      ..result = WeatherSnapshot.fromRow(row, expectedFarmId: 'farm-a');
    final controller = WeatherController(
      repository: repository,
      clock: () => localFetchedAt.add(const Duration(minutes: 1)),
    );
    await controller.load(locatedFarm);
    await tester.pumpWidget(_app(controller));

    expect(find.text('Mis à jour le 01/02/2026 03:04'), findsOneWidget);
    expect(find.text('sur 61 s'), findsOneWidget);
    controller.dispose();
  });

  testWidgets('fresh cached data remains visible with an offline badge', (
    tester,
  ) async {
    final repository = FakeWeatherRepository()..result = weatherSnapshot();
    final controller = WeatherController(
      repository: repository,
      clock: () => DateTime.parse('2026-09-24T10:10:00Z'),
    );
    await controller.load(locatedFarm);
    repository.error = const WeatherFailure(WeatherFailureType.network);
    await controller.refresh();
    await tester.pumpWidget(_app(controller));
    expect(find.text('À jour'), findsOneWidget);
    expect(find.text('Hors ligne'), findsOneWidget);
    expect(find.text('24.3'), findsOneWidget);
    controller.dispose();
  });

  testWidgets('states stale and offline availability with text and icons', (
    tester,
  ) async {
    final repository = FakeWeatherRepository()..result = weatherSnapshot();
    final controller = WeatherController(
      repository: repository,
      clock: () => DateTime.parse('2026-09-24T10:30:00Z'),
    );
    await controller.load(locatedFarm);
    repository.error = const WeatherFailure(WeatherFailureType.network);
    await controller.refresh();
    await tester.pumpWidget(_app(controller));
    expect(find.text('Données anciennes'), findsOneWidget);
    expect(find.text('Hors ligne'), findsOneWidget);
    expect(find.byIcon(Icons.history_rounded), findsOneWidget);
    expect(find.byIcon(Icons.wifi_off_rounded), findsOneWidget);
    controller.dispose();
  });

  testWidgets('missing location is explicit and performs no request', (
    tester,
  ) async {
    final repository = FakeWeatherRepository();
    final controller = WeatherController(repository: repository);
    await controller.load(Farm(id: 'farm-a', name: 'Ferme A'));
    await tester.pumpWidget(_app(controller));
    expect(find.text('Localisation non configurée'), findsOneWidget);
    expect(repository.calls, 0);
    controller.dispose();
  });

  testWidgets('no snapshot is an empty state whose retry fetches again', (
    tester,
  ) async {
    final repository = FakeWeatherRepository();
    final controller = WeatherController(repository: repository);
    await controller.load(locatedFarm);
    await tester.pumpWidget(_app(controller));
    expect(
      find.text('Les données météo ne sont pas encore disponibles.'),
      findsOneWidget,
    );
    await tester.tap(find.text('Réessayer'));
    await tester.pump();
    expect(repository.calls, 2);
    controller.dispose();
  });

  testWidgets('expired data is masked and offers retry', (tester) async {
    final repository = FakeWeatherRepository()..result = weatherSnapshot();
    final controller = WeatherController(
      repository: repository,
      clock: () => DateTime.parse('2026-09-24T11:00:00.001Z'),
    );
    await controller.load(locatedFarm);
    await tester.pumpWidget(_app(controller));
    expect(find.text('Météo indisponible'), findsOneWidget);
    expect(find.text('24.3'), findsNothing);
    expect(find.text('Réessayer'), findsOneWidget);
    controller.dispose();
  });

  testWidgets('network failure without data is explicitly offline', (
    tester,
  ) async {
    final repository = FakeWeatherRepository()
      ..error = const WeatherFailure(WeatherFailureType.network);
    final controller = WeatherController(repository: repository);
    await controller.load(locatedFarm);
    await tester.pumpWidget(_app(controller));
    expect(find.text('Météo hors ligne'), findsOneWidget);
    expect(find.textContaining('sans connexion'), findsOneWidget);
    expect(find.text('Réessayer'), findsOneWidget);
    controller.dispose();
  });

  testWidgets('remains usable on a narrow screen with large French text', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 480));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final repository = FakeWeatherRepository()..result = weatherSnapshot();
    final controller = WeatherController(
      repository: repository,
      clock: () => DateTime.parse('2026-09-24T10:10:00Z'),
    );
    await controller.load(locatedFarm);
    await tester.pumpWidget(_app(controller, textScale: 2));
    expect(find.text('Précipitations actuelles'), findsOneWidget);
    expect(find.text('Actualiser la météo'), findsOneWidget);
    expect(tester.takeException(), isNull);
    controller.dispose();
  });
}
