import 'package:agrimind/features/farm_manager/application/farm_manager_repository.dart';
import 'package:agrimind/features/farm_manager/domain/farm_manager_failure.dart';
import 'package:agrimind/features/farm_manager/domain/farm_summary.dart';
import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';
import 'package:flutter/foundation.dart';

enum FarmManagerStatus { idle, loading, loaded, empty, failure }

final class FarmManagerController extends ChangeNotifier {
  FarmManagerController(this._repository);

  final FarmManagerRepository _repository;
  FarmManagerStatus _status = FarmManagerStatus.idle;
  List<FarmTree> _trees = const [];
  FarmSummary? _summary;
  String? _farmId;

  FarmManagerStatus get status => _status;
  List<FarmTree> get trees => _trees;
  FarmSummary? get summary => _summary;

  Future<void> load(String farmId) async {
    if (_status == FarmManagerStatus.loading) return;
    _farmId = farmId;
    _status = FarmManagerStatus.loading;
    notifyListeners();
    try {
      final results = await Future.wait<Object>([
        _repository.listTrees(farmId),
        _repository.getFarmSummary(farmId),
      ]);
      if (_farmId != farmId) return;
      _trees = results[0] as List<FarmTree>;
      _summary = results[1] as FarmSummary;
      _status = _trees.isEmpty
          ? FarmManagerStatus.empty
          : FarmManagerStatus.loaded;
    } on Object {
      if (_farmId != farmId) return;
      _trees = const [];
      _summary = null;
      _status = FarmManagerStatus.failure;
    }
    notifyListeners();
  }

  Future<void> retry() async {
    final farmId = _farmId;
    if (farmId != null) await load(farmId);
  }
}

enum TreeDetailStatus { idle, loading, loaded, notFound, failure }

final class TreeDetailController extends ChangeNotifier {
  TreeDetailController(this._repository);

  final FarmManagerRepository _repository;
  TreeDetailStatus _status = TreeDetailStatus.idle;
  FarmTree? _tree;
  String? _farmId;
  String? _treeId;

  TreeDetailStatus get status => _status;
  FarmTree? get tree => _tree;

  Future<void> load({required String farmId, required String treeId}) async {
    if (_status == TreeDetailStatus.loading) return;
    _farmId = farmId;
    _treeId = treeId;
    _status = TreeDetailStatus.loading;
    notifyListeners();
    try {
      final tree = await _repository.getTree(farmId: farmId, treeId: treeId);
      if (_farmId != farmId || _treeId != treeId) return;
      if (tree != null && tree.farmId != farmId) {
        _tree = null;
        _status = TreeDetailStatus.notFound;
      } else {
        _tree = tree;
        _status = tree == null
            ? TreeDetailStatus.notFound
            : TreeDetailStatus.loaded;
      }
    } on FarmManagerFailure {
      if (_farmId != farmId || _treeId != treeId) return;
      _tree = null;
      _status = TreeDetailStatus.failure;
    } on Object {
      if (_farmId != farmId || _treeId != treeId) return;
      _tree = null;
      _status = TreeDetailStatus.failure;
    }
    notifyListeners();
  }

  Future<void> retry() async {
    final farmId = _farmId;
    final treeId = _treeId;
    if (farmId != null && treeId != null) {
      await load(farmId: farmId, treeId: treeId);
    }
  }
}
