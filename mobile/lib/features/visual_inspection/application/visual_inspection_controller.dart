import 'package:agrimind/features/visual_inspection/application/cv_inference_repository.dart';
import 'package:agrimind/features/visual_inspection/application/inspection_image_source.dart';
import 'package:agrimind/features/visual_inspection/application/inspection_image_validator.dart';
import 'package:agrimind/features/visual_inspection/domain/cv_inference_result.dart';
import 'package:agrimind/features/visual_inspection/domain/inspection_image.dart';
import 'package:flutter/foundation.dart';

enum VisualInspectionStatus {
  empty,
  selecting,
  ready,
  analyzing,
  result,
  error,
}

final class VisualInspectionController extends ChangeNotifier {
  VisualInspectionController({
    required this.farmId,
    required this.treeId,
    required this.repository,
    required this.imageSource,
    required this.validator,
  });

  final String farmId;
  final String treeId;
  final CvInferenceRepository repository;
  final InspectionImageSource imageSource;
  final InspectionImageValidator validator;

  VisualInspectionStatus status = VisualInspectionStatus.empty;
  InspectionImage? image;
  CvInferenceResult? result;
  String? errorMessage;

  Future<void> selectImage() async {
    if (status == VisualInspectionStatus.selecting ||
        status == VisualInspectionStatus.analyzing) {
      return;
    }
    status = VisualInspectionStatus.selecting;
    errorMessage = null;
    notifyListeners();
    try {
      final selected = await imageSource.selectFromGallery();
      if (selected == null) {
        status = image == null
            ? VisualInspectionStatus.empty
            : VisualInspectionStatus.ready;
        notifyListeners();
        return;
      }
      await validator.validate(selected);
      image = selected;
      result = null;
      status = VisualInspectionStatus.ready;
    } on InspectionImageValidationFailure catch (failure) {
      image = null;
      result = null;
      status = VisualInspectionStatus.error;
      errorMessage = failure.message;
    } on Object {
      status = VisualInspectionStatus.error;
      errorMessage = 'L’image n’a pas pu être sélectionnée.';
    }
    notifyListeners();
  }

  Future<void> analyze() async {
    final selected = image;
    if (selected == null || status == VisualInspectionStatus.analyzing) return;
    status = VisualInspectionStatus.analyzing;
    errorMessage = null;
    result = null;
    notifyListeners();
    try {
      result = await repository.analyze(
        farmId: farmId,
        treeId: treeId,
        image: selected,
      );
      status = VisualInspectionStatus.result;
    } on CvInferenceFailure catch (failure) {
      status = VisualInspectionStatus.error;
      errorMessage = failure.message;
    } on Object {
      status = VisualInspectionStatus.error;
      errorMessage = 'L’analyse est indisponible. Veuillez réessayer.';
    }
    notifyListeners();
  }

  Future<void> retry() => image == null ? selectImage() : analyze();
}
