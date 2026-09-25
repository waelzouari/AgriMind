import 'package:agrimind/features/history/application/history_repository.dart';
import 'package:agrimind/features/history/domain/history_snapshot.dart';
import 'package:agrimind/features/visual_inspection/domain/cv_inference_result.dart';

/// Development-only deterministic data. No cloud records are read or written.
final class DemoHistoryRepository implements HistoryRepository {
  const DemoHistoryRepository();

  @override
  Future<HistorySnapshot> load(String farmId) async => HistorySnapshot(
    sensors: [
      SensorHistoryEntry(
        label: 'Humidité du sol',
        value: '42 %',
        recordedAt: DateTime.utc(2026, 9, 25, 8, 30),
      ),
      SensorHistoryEntry(
        label: 'Température',
        value: '24,5 °C',
        recordedAt: DateTime.utc(2026, 9, 25, 8, 15),
      ),
    ],
    irrigations: [
      IrrigationHistoryEntry(
        before: 36,
        after: 43,
        completedAt: DateTime.utc(2026, 9, 24, 18),
      ),
    ],
    inspections: [
      InspectionHistoryEntry(
        treeLabel: 'Olivier A1',
        classification: CvClassification.normal,
        completedAt: DateTime.utc(2026, 9, 24, 10),
      ),
      InspectionHistoryEntry(
        treeLabel: 'Olivier A2',
        classification: CvClassification.anomaly,
        completedAt: DateTime.utc(2026, 9, 23, 16, 45),
      ),
    ],
  );
}
