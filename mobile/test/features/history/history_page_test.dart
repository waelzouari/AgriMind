import 'dart:async';

import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/features/history/application/history_controller.dart';
import 'package:agrimind/features/history/application/history_repository.dart';
import 'package:agrimind/features/history/domain/history_snapshot.dart';
import 'package:agrimind/features/history/presentation/history_page.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/visual_inspection/domain/cv_inference_result.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

final farm = Farm(id: 'farm-a', name: 'Ferme de Sfax');

final class _Repository implements HistoryRepository {
  _Repository({
    this.snapshot = const HistorySnapshot(),
    this.failure,
    this.pending,
  });
  HistorySnapshot snapshot;
  HistoryFailure? failure;
  Completer<HistorySnapshot>? pending;
  String? requestedFarmId;
  int calls = 0;
  @override
  Future<HistorySnapshot> load(String farmId) async {
    calls += 1;
    requestedFarmId = farmId;
    if (failure case final value?) throw value;
    if (pending case final value?) return value.future;
    return snapshot;
  }
}

Widget _app(_Repository repository, {bool demo = false}) => MaterialApp(
  theme: AgriMindTheme.light,
  home: HistoryPage(
    farm: farm,
    demonstrationMode: demo,
    controller: HistoryController(farmId: farm.id, repository: repository),
    onHome: () {},
    onFarm: () {},
  ),
);

void main() {
  testWidgets('shows loading while the farm-scoped request is pending', (
    tester,
  ) async {
    final pending = Completer<HistorySnapshot>();
    final repository = _Repository(pending: pending);
    await tester.pumpWidget(_app(repository));
    await tester.pump();
    expect(find.text('Chargement de l’historique'), findsOneWidget);
    expect(repository.requestedFarmId, farm.id);
    pending.complete(const HistorySnapshot());
    await tester.pumpAndSettle();
  });

  testWidgets('renders sensor irrigation and safe inspection history', (
    tester,
  ) async {
    final repository = _Repository(
      snapshot: HistorySnapshot(
        sensors: [
          SensorHistoryEntry(
            label: 'Humidité du sol',
            value: '42 %',
            recordedAt: DateTime.utc(2026, 9, 25),
          ),
        ],
        irrigations: [
          IrrigationHistoryEntry(
            before: 35,
            after: 42,
            completedAt: DateTime.utc(2026, 9, 24),
          ),
        ],
        inspections: [
          InspectionHistoryEntry(
            treeLabel: 'Olivier A1',
            classification: CvClassification.anomaly,
            completedAt: DateTime.utc(2026, 9, 23),
            anomalySoftmaxProbability: 0.7,
          ),
        ],
      ),
    );
    await tester.pumpWidget(_app(repository, demo: true));
    await tester.pumpAndSettle();
    expect(find.text('Capteurs'), findsNWidgets(2));
    expect(find.text('Irrigation'), findsNWidgets(2));
    expect(find.text('Inspections visuelles'), findsOneWidget);
    expect(find.text('ANOMALY'), findsOneWidget);
    expect(find.textContaining('score non calibré'), findsOneWidget);
    expect(find.textContaining('événements sont simulés'), findsOneWidget);
    expect(find.textContaining('maladie'), findsNothing);
  });

  testWidgets('shows a complete empty state', (tester) async {
    await tester.pumpWidget(_app(_Repository()));
    await tester.pumpAndSettle();
    expect(find.text('Aucun événement'), findsOneWidget);
  });

  testWidgets('shows per-category empty states', (tester) async {
    await tester.pumpWidget(
      _app(
        _Repository(
          snapshot: HistorySnapshot(
            sensors: [
              SensorHistoryEntry(
                label: 'Température',
                value: '24 °C',
                recordedAt: DateTime.utc(2026),
              ),
            ],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Aucun événement'), findsNWidgets(2));
  });

  testWidgets('shows an error and recovers on retry', (tester) async {
    final repository = _Repository(
      failure: const HistoryFailure('Service indisponible.'),
    );
    await tester.pumpWidget(_app(repository));
    await tester.pumpAndSettle();
    expect(find.text('Historique indisponible'), findsOneWidget);
    repository.failure = null;
    repository.snapshot = HistorySnapshot(
      sensors: [
        SensorHistoryEntry(
          label: 'Température',
          value: '24 °C',
          recordedAt: DateTime.utc(2026),
        ),
      ],
    );
    await tester.tap(find.text('Réessayer'));
    await tester.pumpAndSettle();
    expect(find.text('Température'), findsOneWidget);
    expect(repository.calls, 2);
  });
}
