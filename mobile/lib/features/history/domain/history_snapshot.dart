import 'package:agrimind/features/visual_inspection/domain/cv_inference_result.dart';

final class SensorHistoryEntry {
  const SensorHistoryEntry({
    required this.label,
    required this.value,
    required this.recordedAt,
  });
  final String label;
  final String value;
  final DateTime recordedAt;
}

final class IrrigationHistoryEntry {
  const IrrigationHistoryEntry({
    required this.before,
    required this.after,
    required this.completedAt,
  });
  final double before;
  final double after;
  final DateTime completedAt;
}

final class InspectionHistoryEntry {
  const InspectionHistoryEntry({
    required this.treeLabel,
    required this.classification,
    required this.completedAt,
    this.anomalySoftmaxProbability,
  });
  final String treeLabel;
  final CvClassification classification;
  final DateTime completedAt;
  final double? anomalySoftmaxProbability;
}

final class HistorySnapshot {
  const HistorySnapshot({
    this.sensors = const [],
    this.irrigations = const [],
    this.inspections = const [],
  });
  final List<SensorHistoryEntry> sensors;
  final List<IrrigationHistoryEntry> irrigations;
  final List<InspectionHistoryEntry> inspections;
  bool get isEmpty =>
      sensors.isEmpty && irrigations.isEmpty && inspections.isEmpty;
}
