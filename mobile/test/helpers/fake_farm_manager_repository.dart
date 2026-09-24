import 'package:agrimind/features/farm_manager/application/farm_manager_repository.dart';
import 'package:agrimind/features/farm_manager/domain/farm_summary.dart';
import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';

final class FakeFarmManagerRepository implements FarmManagerRepository {
  FakeFarmManagerRepository({this.trees = const []});

  List<FarmTree> trees;
  Object? error;
  int listCalls = 0;
  int getCalls = 0;

  @override
  Future<List<FarmTree>> listTrees(String farmId) async {
    listCalls += 1;
    if (error case final failure?) throw failure;
    return trees.where((tree) => tree.farmId == farmId).toList();
  }

  @override
  Future<FarmTree?> getTree({
    required String farmId,
    required String treeId,
  }) async {
    getCalls += 1;
    if (error case final failure?) throw failure;
    for (final tree in trees) {
      if (tree.farmId == farmId && tree.id == treeId) return tree;
    }
    return null;
  }

  @override
  Future<FarmSummary> getFarmSummary(String farmId) async {
    if (error case final failure?) throw failure;
    return FarmSummary(
      totalTrees: trees.where((tree) => tree.farmId == farmId).length,
    );
  }
}
