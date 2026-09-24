import 'dart:async';

import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/features/farm_manager/application/farm_manager_repository.dart';
import 'package:agrimind/features/farm_manager/domain/farm_manager_failure.dart';
import 'package:agrimind/features/farm_manager/domain/farm_summary.dart';
import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';
import 'package:agrimind/features/farm_manager/domain/tree_position.dart';
import 'package:agrimind/features/farm_manager/presentation/farm_manager_page.dart';
import 'package:agrimind/features/farm_manager/presentation/tree_detail_page.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_farm_manager_repository.dart';

final farm = Farm(id: 'farm-a', name: 'Ferme de Sfax');
const treeA1 = FarmTree(
  id: '11111111-1111-4111-8111-111111111111',
  farmId: 'farm-a',
  label: 'Olivier A1',
  position: TreePosition(row: 1, column: 1),
);
const treeA2 = FarmTree(
  id: '22222222-2222-4222-8222-222222222222',
  farmId: 'farm-a',
  label: 'Olivier A2',
  position: TreePosition(row: 1, column: 2),
);
const treeB1 = FarmTree(
  id: '33333333-3333-4333-8333-333333333333',
  farmId: 'farm-a',
  label: 'Olivier B1',
  position: TreePosition(row: 2, column: 1),
);

Widget testApp(Widget home) =>
    MaterialApp(theme: AgriMindTheme.light, home: home);

final class _PendingRepository implements FarmManagerRepository {
  final treesCompleter = Completer<List<FarmTree>>();
  final summaryCompleter = Completer<FarmSummary>();
  final treeCompleter = Completer<FarmTree?>();

  @override
  Future<List<FarmTree>> listTrees(String farmId) => treesCompleter.future;

  @override
  Future<FarmSummary> getFarmSummary(String farmId) => summaryCompleter.future;

  @override
  Future<FarmTree?> getTree({required String farmId, required String treeId}) =>
      treeCompleter.future;
}

final class _WrongFarmRepository implements FarmManagerRepository {
  @override
  Future<FarmTree?> getTree({
    required String farmId,
    required String treeId,
  }) async => const FarmTree(
    id: '44444444-4444-4444-8444-444444444444',
    farmId: 'farm-b',
    label: 'Wrong farm',
    position: TreePosition(row: 1, column: 1),
  );

  @override
  Future<FarmSummary> getFarmSummary(String farmId) async =>
      const FarmSummary(totalTrees: 0);

  @override
  Future<List<FarmTree>> listTrees(String farmId) async => const [];
}

void main() {
  testWidgets('Farm Manager shows loading then honest empty state', (
    tester,
  ) async {
    final repository = _PendingRepository();
    await tester.pumpWidget(
      testApp(FarmManagerPage(farm: farm, repository: repository)),
    );

    expect(find.text('Chargement de la ferme'), findsOneWidget);
    repository.treesCompleter.complete(const []);
    repository.summaryCompleter.complete(const FarmSummary(totalTrees: 0));
    await tester.pumpAndSettle();

    expect(find.text('0'), findsOneWidget);
    expect(find.text('Aucun arbre configuré'), findsOneWidget);
    expect(find.text('Healthy'), findsNothing);
    expect(find.text('Normal'), findsNothing);
  });

  testWidgets('renders real total and ordered neutral tree grid', (
    tester,
  ) async {
    final repository = FakeFarmManagerRepository(
      trees: const [treeA1, treeA2, treeB1],
    );
    await tester.pumpWidget(
      testApp(FarmManagerPage(farm: farm, repository: repository)),
    );
    await tester.pumpAndSettle();

    expect(find.text('Ferme de Sfax'), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
    expect(find.text('A1'), findsOneWidget);
    expect(find.text('A2'), findsOneWidget);
    expect(find.text('B1'), findsOneWidget);
    expect(
      tester.getTopLeft(find.text('A1')).dx,
      lessThan(tester.getTopLeft(find.text('A2')).dx),
    );
    expect(
      tester.getTopLeft(find.text('A2')).dx,
      lessThan(tester.getTopLeft(find.text('B1')).dx),
    );
    expect(find.text('—'), findsNWidgets(2));
    expect(find.textContaining('anomal'), findsNothing);
  });

  testWidgets('tree tap opens detail by id and back returns to grid', (
    tester,
  ) async {
    final repository = FakeFarmManagerRepository(trees: const [treeA1]);
    await tester.pumpWidget(
      testApp(FarmManagerPage(farm: farm, repository: repository)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(Key('farm-tree-${treeA1.id}')));
    await tester.pumpAndSettle();

    expect(repository.getCalls, 1);
    expect(find.byType(TreeDetailPage), findsOneWidget);
    expect(find.text('Olivier A1'), findsNWidgets(2));
    expect(find.text('Position A1'), findsOneWidget);

    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    expect(find.byType(FarmManagerPage), findsOneWidget);
  });

  testWidgets('Farm Manager maps repository failure to safe retry state', (
    tester,
  ) async {
    final repository = FakeFarmManagerRepository()
      ..error = const FarmManagerFailure(FarmManagerFailureType.unavailable);
    await tester.pumpWidget(
      testApp(FarmManagerPage(farm: farm, repository: repository)),
    );
    await tester.pumpAndSettle();

    expect(find.text('Ferme indisponible'), findsOneWidget);
    expect(find.text('Réessayer'), findsOneWidget);
  });

  testWidgets('Tree Detail shows loading and supported identity only', (
    tester,
  ) async {
    final repository = _PendingRepository();
    await tester.pumpWidget(
      testApp(
        TreeDetailPage(farm: farm, treeId: treeA1.id, repository: repository),
      ),
    );
    expect(find.text('Chargement de l’arbre'), findsOneWidget);

    repository.treeCompleter.complete(treeA1);
    await tester.pumpAndSettle();

    expect(find.text('Olivier A1'), findsNWidgets(2));
    expect(find.text('Position A1'), findsOneWidget);
    expect(find.text('Statut'), findsOneWidget);
    expect(find.text('Humidité du sol'), findsOneWidget);
    expect(find.text('Dernière irrigation'), findsOneWidget);
    expect(find.text('Dernière inspection'), findsOneWidget);
    expect(find.text('Indisponible'), findsNWidgets(4));
    expect(find.text('Aucune activité disponible'), findsOneWidget);
    expect(find.textContaining('61'), findsNothing);
    expect(find.textContaining('NORMAL'), findsNothing);
    expect(find.textContaining('07:30'), findsNothing);
    expect(
      tester.widget<ElevatedButton>(find.byType(ElevatedButton)).onPressed,
      isNull,
    );
  });

  testWidgets('Tree Detail distinguishes not found from repository failure', (
    tester,
  ) async {
    final missing = FakeFarmManagerRepository();
    await tester.pumpWidget(
      testApp(
        TreeDetailPage(farm: farm, treeId: treeA1.id, repository: missing),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Arbre introuvable'), findsOneWidget);

    await tester.pumpWidget(const SizedBox());
    final failing = FakeFarmManagerRepository()
      ..error = const FarmManagerFailure(FarmManagerFailureType.unauthorized);
    await tester.pumpWidget(
      testApp(
        TreeDetailPage(farm: farm, treeId: treeA1.id, repository: failing),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Arbre indisponible'), findsOneWidget);
  });

  testWidgets('Tree Detail rejects a tree from another farm', (tester) async {
    await tester.pumpWidget(
      testApp(
        TreeDetailPage(
          farm: farm,
          treeId: treeA1.id,
          repository: _WrongFarmRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Arbre introuvable'), findsOneWidget);
    expect(find.text('Wrong farm'), findsNothing);
  });

  testWidgets('critical pages do not overflow on a narrow scaled phone', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 568));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final repository = FakeFarmManagerRepository(
      trees: const [treeA1, treeA2, treeB1],
    );
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(1.2)),
        child: testApp(FarmManagerPage(farm: farm, repository: repository)),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    await tester.tap(find.byKey(Key('farm-tree-${treeA1.id}')));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
