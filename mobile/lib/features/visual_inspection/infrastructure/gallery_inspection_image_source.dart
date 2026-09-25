import 'package:agrimind/features/visual_inspection/application/inspection_image_source.dart';
import 'package:agrimind/features/visual_inspection/domain/inspection_image.dart';
import 'package:image_picker/image_picker.dart';

final class GalleryInspectionImageSource implements InspectionImageSource {
  GalleryInspectionImageSource([ImagePicker? picker])
    : _picker = picker ?? ImagePicker();

  final ImagePicker _picker;

  @override
  Future<InspectionImage?> selectFromGallery() async {
    final file = await _picker.pickImage(source: ImageSource.gallery);
    if (file == null) return null;
    return InspectionImage(
      bytes: await file.readAsBytes(),
      fileName: file.name,
      mimeType: file.mimeType,
    );
  }
}
