import 'package:agrimind/features/visual_inspection/application/cv_inference_repository.dart';
import 'package:agrimind/features/visual_inspection/domain/cv_inference_result.dart';
import 'package:agrimind/features/visual_inspection/domain/inspection_image.dart';

/// Deterministic development-only adapter. It never calls a model or network.
final class DemoCvInferenceRepository implements CvInferenceRepository {
  const DemoCvInferenceRepository();

  @override
  Future<CvInferenceResult> analyze({
    required String farmId,
    required String treeId,
    required InspectionImage image,
  }) async {
    final checksum = image.bytes.fold<int>(0, (sum, byte) => (sum + byte) % 2);
    return CvInferenceResult(
      classification: checksum == 0
          ? CvClassification.normal
          : CvClassification.anomaly,
    );
  }
}
