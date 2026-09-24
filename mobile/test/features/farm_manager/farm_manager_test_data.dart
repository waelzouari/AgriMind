import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';
import 'package:agrimind/features/farm_manager/domain/tree_position.dart';

const testFarmId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';

List<FarmTree> twelveTreeGridFixture() => [
  for (var row = 1; row <= 3; row += 1)
    for (var column = 1; column <= 4; column += 1)
      FarmTree(
        id: '00000000-0000-4000-8000-${(row * 100 + column).toString().padLeft(12, '0')}',
        farmId: testFarmId,
        label: 'Tree ${String.fromCharCode(64 + row)}$column',
        position: TreePosition(row: row, column: column),
      ),
];
