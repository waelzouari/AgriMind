import 'dart:typed_data';

final class InspectionImage {
  const InspectionImage({
    required this.bytes,
    required this.fileName,
    required this.mimeType,
  });

  final Uint8List bytes;
  final String fileName;
  final String? mimeType;
}
