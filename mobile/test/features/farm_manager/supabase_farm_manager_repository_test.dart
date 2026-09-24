import 'package:agrimind/features/farm_manager/domain/farm_manager_failure.dart';
import 'package:agrimind/features/farm_manager/infrastructure/supabase_farm_manager_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

const farmId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const treeA1Id = '11111111-1111-4111-8111-111111111111';
const treeA2Id = '22222222-2222-4222-8222-222222222222';
const treeB1Id = '33333333-3333-4333-8333-333333333333';

final class _RowSource implements FarmManagerRowSource {
  List<Map<String, dynamic>> rows = [];
  Map<String, dynamic>? row;
  Object? error;
  String? listedFarmId;
  String? requestedFarmId;
  String? requestedTreeId;

  @override
  Future<List<Map<String, dynamic>>> listTrees(String farmId) async {
    listedFarmId = farmId;
    if (error case final failure?) throw failure;
    return rows;
  }

  @override
  Future<Map<String, dynamic>?> getTree({
    required String farmId,
    required String treeId,
  }) async {
    requestedFarmId = farmId;
    requestedTreeId = treeId;
    if (error case final failure?) throw failure;
    return row;
  }
}

Map<String, dynamic> treeRow({
  String id = treeA1Id,
  String ownerFarmId = farmId,
  String label = 'Olive A1',
  int row = 1,
  int column = 1,
}) => {
  'id': id,
  'farm_id': ownerFarmId,
  'label': label,
  'grid_row': row,
  'grid_column': column,
};

void main() {
  test('maps Supabase rows and returns deterministic grid ordering', () async {
    final source = _RowSource()
      ..rows = [
        treeRow(id: treeB1Id, label: 'B1', row: 2),
        treeRow(id: treeA2Id, label: 'A2', column: 2),
        treeRow(label: 'A1'),
      ];

    final trees = await SupabaseFarmManagerRepository(source).listTrees(farmId);

    expect(source.listedFarmId, farmId);
    expect(trees.map((tree) => tree.position.displayLabel), ['A1', 'A2', 'B1']);
    expect(trees.first.label, 'A1');
    expect(() => trees.add(trees.first), throwsUnsupportedError);
  });

  test(
    'returns a valid empty list and zero summary for an empty farm',
    () async {
      final repository = SupabaseFarmManagerRepository(_RowSource());

      expect(await repository.listTrees(farmId), isEmpty);
      expect((await repository.getFarmSummary(farmId)).totalTrees, 0);
    },
  );

  test('derives the farm summary from tree rows', () async {
    final source = _RowSource()..rows = [treeRow(), treeRow(id: treeA2Id)];

    final summary = await SupabaseFarmManagerRepository(
      source,
    ).getFarmSummary(farmId);

    expect(summary.totalTrees, 2);
  });

  test('gets one tree by farm and stable UUID', () async {
    final source = _RowSource()..row = treeRow();

    final tree = await SupabaseFarmManagerRepository(
      source,
    ).getTree(farmId: farmId, treeId: treeA1Id);

    expect(source.requestedFarmId, farmId);
    expect(source.requestedTreeId, treeA1Id);
    expect(tree?.id, treeA1Id);
    expect(tree?.position.displayLabel, 'A1');
  });

  test('returns null when the requested tree is not found', () async {
    final tree = await SupabaseFarmManagerRepository(
      _RowSource(),
    ).getTree(farmId: farmId, treeId: treeA1Id);

    expect(tree, isNull);
  });

  test('rejects invalid or cross-farm row data', () async {
    final cases = [
      treeRow(id: 'not-a-uuid'),
      treeRow(ownerFarmId: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'),
      treeRow(label: '  '),
      treeRow(row: 0),
      treeRow(column: 100),
    ];

    for (final invalidRow in cases) {
      final source = _RowSource()..rows = [invalidRow];
      await expectLater(
        SupabaseFarmManagerRepository(source).listTrees(farmId),
        throwsA(
          isA<FarmManagerFailure>().having(
            (failure) => failure.type,
            'type',
            FarmManagerFailureType.invalidData,
          ),
        ),
      );
    }
  });

  test('rejects an unexpected identity from getTree', () async {
    final source = _RowSource()..row = treeRow(id: treeA2Id);

    await expectLater(
      SupabaseFarmManagerRepository(
        source,
      ).getTree(farmId: farmId, treeId: treeA1Id),
      throwsA(
        isA<FarmManagerFailure>().having(
          (failure) => failure.type,
          'type',
          FarmManagerFailureType.invalidData,
        ),
      ),
    );
  });

  test(
    'maps Supabase and unexpected failures without leaking details',
    () async {
      const cases = {
        '42501': FarmManagerFailureType.unauthorized,
        '08006': FarmManagerFailureType.unavailable,
        'PGRST000': FarmManagerFailureType.unavailable,
        'XX000': FarmManagerFailureType.unknown,
      };
      for (final entry in cases.entries) {
        final source = _RowSource()
          ..error = PostgrestException(
            message: 'sensitive provider detail',
            code: entry.key,
          );
        await expectLater(
          SupabaseFarmManagerRepository(source).listTrees(farmId),
          throwsA(
            isA<FarmManagerFailure>().having(
              (failure) => failure.type,
              'type',
              entry.value,
            ),
          ),
        );
      }

      final source = _RowSource()..error = StateError('provider detail');
      await expectLater(
        SupabaseFarmManagerRepository(source).listTrees(farmId),
        throwsA(
          isA<FarmManagerFailure>().having(
            (failure) => failure.type,
            'type',
            FarmManagerFailureType.unknown,
          ),
        ),
      );
    },
  );
}
