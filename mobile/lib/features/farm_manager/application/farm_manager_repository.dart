import 'package:agrimind/features/farm_manager/domain/farm_summary.dart';
import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';

abstract interface class FarmManagerRepository {
  Future<List<FarmTree>> listTrees(String farmId);

  Future<FarmTree?> getTree({required String farmId, required String treeId});

  Future<FarmSummary> getFarmSummary(String farmId);
}
