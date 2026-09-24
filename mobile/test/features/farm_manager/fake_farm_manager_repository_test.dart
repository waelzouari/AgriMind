import 'package:agrimind/features/farm_manager/application/farm_manager_repository.dart';
import 'package:agrimind/features/farm_manager/domain/farm_summary.dart';
import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';
import 'package:agrimind/features/farm_manager/domain/tree_position.dart';
import 'package:flutter_test/flutter_test.dart';

import 'farm_manager_test_data.dart';

final class _FakeFarmManagerRepository implements FarmManagerRepository {
  _FakeFarmManagerRepository(this.trees);

  final List<FarmTree> trees;

  @override
  Future<FarmTree?> getTree({
    required String farmId,
    required String treeId,
  }) async {
    for (final tree in trees) {
      if (tree.farmId == farmId && tree.id == treeId) return tree;
    }
    return null;
  }

  @override
  Future<FarmSummary> getFarmSummary(String farmId) async => FarmSummary(
    totalTrees: trees.where((tree) => tree.farmId == farmId).length,
  );

  @override
  Future<List<FarmTree>> listTrees(String farmId) async =>
      trees.where((tree) => tree.farmId == farmId).toList();
}

void main() {
  test('repository boundary is replaceable by a deterministic fake', () async {
    const tree = FarmTree(
      id: '11111111-1111-4111-8111-111111111111',
      farmId: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      label: 'Tree A1',
      position: TreePosition(row: 1, column: 1),
    );
    final repository = _FakeFarmManagerRepository([tree]);

    expect(await repository.listTrees(tree.farmId), [tree]);
    expect(
      await repository.getTree(farmId: tree.farmId, treeId: tree.id),
      tree,
    );
    expect((await repository.getFarmSummary(tree.farmId)).totalTrees, 1);
  });

  test('test-only fixture represents the A1 through C4 mockup grid', () {
    final fixture = twelveTreeGridFixture();

    expect(fixture, hasLength(12));
    expect(fixture.map((tree) => tree.position.displayLabel), [
      'A1',
      'A2',
      'A3',
      'A4',
      'B1',
      'B2',
      'B3',
      'B4',
      'C1',
      'C2',
      'C3',
      'C4',
    ]);
  });
}
