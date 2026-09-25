import 'package:agrimind/features/history/application/history_repository.dart';
import 'package:agrimind/features/history/domain/history_snapshot.dart';
import 'package:flutter/foundation.dart';

enum HistoryStatus { idle, loading, loaded, empty, failure }

final class HistoryController extends ChangeNotifier {
  HistoryController({required this.farmId, required this.repository});
  final String farmId;
  final HistoryRepository repository;
  HistoryStatus status = HistoryStatus.idle;
  HistorySnapshot snapshot = const HistorySnapshot();
  String? errorMessage;

  Future<void> load() async {
    if (status == HistoryStatus.loading) return;
    status = HistoryStatus.loading;
    errorMessage = null;
    notifyListeners();
    try {
      snapshot = await repository.load(farmId);
      status = snapshot.isEmpty ? HistoryStatus.empty : HistoryStatus.loaded;
    } on HistoryFailure catch (failure) {
      status = HistoryStatus.failure;
      errorMessage = failure.message;
    } on Object {
      status = HistoryStatus.failure;
      errorMessage = 'L’historique ne peut pas être chargé.';
    }
    notifyListeners();
  }
}
