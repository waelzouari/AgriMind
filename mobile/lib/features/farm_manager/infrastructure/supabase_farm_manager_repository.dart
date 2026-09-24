import 'package:agrimind/features/farm_manager/application/farm_manager_repository.dart';
import 'package:agrimind/features/farm_manager/domain/farm_manager_failure.dart';
import 'package:agrimind/features/farm_manager/domain/farm_summary.dart';
import 'package:agrimind/features/farm_manager/domain/farm_tree.dart';
import 'package:agrimind/features/farm_manager/domain/tree_position.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

abstract interface class FarmManagerRowSource {
  Future<List<Map<String, dynamic>>> listTrees(String farmId);

  Future<Map<String, dynamic>?> getTree({
    required String farmId,
    required String treeId,
  });
}

final class SupabaseFarmManagerRowSource implements FarmManagerRowSource {
  SupabaseFarmManagerRowSource(this._client);

  final SupabaseClient _client;

  @override
  Future<List<Map<String, dynamic>>> listTrees(String farmId) async {
    final rows = await _client
        .from('trees')
        .select(_treeColumns)
        .eq('farm_id', farmId)
        .order('grid_row')
        .order('grid_column')
        .order('id');
    return rows;
  }

  @override
  Future<Map<String, dynamic>?> getTree({
    required String farmId,
    required String treeId,
  }) => _client
      .from('trees')
      .select(_treeColumns)
      .eq('farm_id', farmId)
      .eq('id', treeId)
      .maybeSingle();
}

final class SupabaseFarmManagerRepository implements FarmManagerRepository {
  SupabaseFarmManagerRepository(this._source);

  final FarmManagerRowSource _source;

  @override
  Future<List<FarmTree>> listTrees(String farmId) async {
    try {
      final trees = (await _source.listTrees(
        farmId,
      )).map((row) => mapFarmTreeRow(row, expectedFarmId: farmId)).toList();
      trees.sort(_compareTrees);
      return List.unmodifiable(trees);
    } on FarmManagerFailure {
      rethrow;
    } on PostgrestException catch (error) {
      throw mapFarmManagerPostgrestException(error);
    } on FormatException {
      throw const FarmManagerFailure(FarmManagerFailureType.invalidData);
    } on Object {
      throw const FarmManagerFailure(FarmManagerFailureType.unknown);
    }
  }

  @override
  Future<FarmTree?> getTree({
    required String farmId,
    required String treeId,
  }) async {
    try {
      final row = await _source.getTree(farmId: farmId, treeId: treeId);
      return row == null
          ? null
          : mapFarmTreeRow(row, expectedFarmId: farmId, expectedTreeId: treeId);
    } on FarmManagerFailure {
      rethrow;
    } on PostgrestException catch (error) {
      throw mapFarmManagerPostgrestException(error);
    } on FormatException {
      throw const FarmManagerFailure(FarmManagerFailureType.invalidData);
    } on Object {
      throw const FarmManagerFailure(FarmManagerFailureType.unknown);
    }
  }

  @override
  Future<FarmSummary> getFarmSummary(String farmId) async =>
      FarmSummary(totalTrees: (await listTrees(farmId)).length);
}

FarmTree mapFarmTreeRow(
  Map<String, dynamic> row, {
  required String expectedFarmId,
  String? expectedTreeId,
}) {
  final id = _nonEmptyString(row, 'id');
  final farmId = _nonEmptyString(row, 'farm_id');
  final label = _nonEmptyString(row, 'label').trim();
  final gridRow = _boundedInteger(row, 'grid_row', min: 1, max: 26);
  final gridColumn = _boundedInteger(row, 'grid_column', min: 1, max: 99);
  if (!_isUuid(id) || !_isUuid(farmId)) {
    throw const FormatException('Tree identifiers must be UUIDs.');
  }
  if (farmId != expectedFarmId ||
      (expectedTreeId != null && id != expectedTreeId)) {
    throw const FormatException('Tree identity mismatch.');
  }
  if (label.length > 120) {
    throw const FormatException('Tree label is too long.');
  }
  return FarmTree(
    id: id,
    farmId: farmId,
    label: label,
    position: TreePosition(row: gridRow, column: gridColumn),
  );
}

FarmManagerFailure mapFarmManagerPostgrestException(PostgrestException error) {
  if (error.code == '42501') {
    return const FarmManagerFailure(FarmManagerFailureType.unauthorized);
  }
  final code = error.code ?? '';
  if (code.startsWith('08') || code.startsWith('PGRST0')) {
    return const FarmManagerFailure(FarmManagerFailureType.unavailable);
  }
  return const FarmManagerFailure(FarmManagerFailureType.unknown);
}

int _compareTrees(FarmTree left, FarmTree right) {
  final position = left.position.compareTo(right.position);
  return position != 0 ? position : left.id.compareTo(right.id);
}

String _nonEmptyString(Map<String, dynamic> row, String field) {
  final value = row[field];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('$field must be a non-empty string.');
  }
  return value;
}

int _boundedInteger(
  Map<String, dynamic> row,
  String field, {
  required int min,
  required int max,
}) {
  final value = row[field];
  if (value is! int || value < min || value > max) {
    throw FormatException('$field is out of range.');
  }
  return value;
}

bool _isUuid(String value) =>
    RegExp(
      r'^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$',
    ).hasMatch(value) &&
    value != '00000000-0000-0000-0000-000000000000';

const _treeColumns = 'id,farm_id,label,grid_row,grid_column';
