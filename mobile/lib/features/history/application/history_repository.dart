import 'package:agrimind/features/history/domain/history_snapshot.dart';

abstract interface class HistoryRepository {
  Future<HistorySnapshot> load(String farmId);
}

final class HistoryFailure implements Exception {
  const HistoryFailure([this.message = 'L’historique est indisponible.']);
  final String message;
}
