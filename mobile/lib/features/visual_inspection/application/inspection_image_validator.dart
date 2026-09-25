import 'dart:ui' as ui;

import 'package:agrimind/features/visual_inspection/domain/inspection_image.dart';

final class InspectionImageValidationFailure implements Exception {
  const InspectionImageValidationFailure(this.message);

  final String message;
}

abstract interface class InspectionImageValidator {
  Future<void> validate(InspectionImage image);
}

final class DefaultInspectionImageValidator
    implements InspectionImageValidator {
  const DefaultInspectionImageValidator();

  static const maxEncodedBytes = 8 * 1024 * 1024;
  static const maxDimension = 4096;
  static const maxPixels = 16000000;

  @override
  Future<void> validate(InspectionImage image) async {
    if (image.bytes.isEmpty) {
      throw const InspectionImageValidationFailure('L’image est vide.');
    }
    if (image.bytes.length > maxEncodedBytes) {
      throw const InspectionImageValidationFailure(
        'L’image dépasse la limite de 8 Mo.',
      );
    }
    if (!_hasSupportedSignature(image)) {
      throw const InspectionImageValidationFailure(
        'Sélectionnez une image JPEG ou PNG valide.',
      );
    }

    ui.Codec? codec;
    try {
      codec = await ui.instantiateImageCodec(image.bytes);
      final frame = await codec.getNextFrame();
      final imageWidth = frame.image.width;
      final imageHeight = frame.image.height;
      frame.image.dispose();
      if (imageWidth <= 0 ||
          imageHeight <= 0 ||
          imageWidth > maxDimension ||
          imageHeight > maxDimension ||
          imageWidth * imageHeight > maxPixels) {
        throw const InspectionImageValidationFailure(
          'L’image dépasse les dimensions autorisées.',
        );
      }
    } on InspectionImageValidationFailure {
      rethrow;
    } on Object {
      throw const InspectionImageValidationFailure(
        'L’image sélectionnée ne peut pas être lue.',
      );
    } finally {
      codec?.dispose();
    }
  }

  bool _hasSupportedSignature(InspectionImage image) {
    final bytes = image.bytes;
    final jpeg =
        bytes.length >= 3 &&
        bytes[0] == 0xff &&
        bytes[1] == 0xd8 &&
        bytes[2] == 0xff;
    final png =
        bytes.length >= 8 &&
        bytes[0] == 0x89 &&
        bytes[1] == 0x50 &&
        bytes[2] == 0x4e &&
        bytes[3] == 0x47 &&
        bytes[4] == 0x0d &&
        bytes[5] == 0x0a &&
        bytes[6] == 0x1a &&
        bytes[7] == 0x0a;
    return jpeg || png;
  }
}
