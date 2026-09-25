import 'package:agrimind/features/visual_inspection/domain/inspection_image.dart';

abstract interface class InspectionImageSource {
  Future<InspectionImage?> selectFromGallery();
}
