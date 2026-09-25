import 'package:agrimind/features/visual_inspection/domain/cv_inference_result.dart';
import 'package:agrimind/features/visual_inspection/domain/inspection_image.dart';

abstract interface class CvInferenceRepository {
  Future<CvInferenceResult> analyze({
    required String farmId,
    required String treeId,
    required InspectionImage image,
  });
}

final class CvInferenceFailure implements Exception {
  const CvInferenceFailure([this.message = 'L’analyse a échoué.']);

  final String message;
}
