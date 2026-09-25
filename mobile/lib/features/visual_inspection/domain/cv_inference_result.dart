enum CvClassification { normal, anomaly }

extension CvClassificationWireValue on CvClassification {
  String get label => switch (this) {
    CvClassification.normal => 'NORMAL',
    CvClassification.anomaly => 'ANOMALY',
  };
}

final class CvInferenceResult {
  const CvInferenceResult({
    required this.classification,
    this.anomalySoftmaxProbability,
    this.modelVersion,
    this.inferenceId,
  });

  final CvClassification classification;

  /// Uncalibrated probability from the model softmax, never a confidence.
  final double? anomalySoftmaxProbability;
  final String? modelVersion;
  final String? inferenceId;
}
