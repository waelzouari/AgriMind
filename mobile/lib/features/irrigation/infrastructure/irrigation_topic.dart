final class IrrigationTopic {
  const IrrigationTopic({required this.farmId, required this.deviceId});
  final String farmId;
  final String deviceId;
  String get base => 'agrimind/v1/farms/$farmId/devices/$deviceId';
  String get command => '$base/commands/pump';
  String get acknowledgementFilter => '$base/acks/+';
  String acknowledgement(String commandId) => '$base/acks/$commandId';

  String? parseAcknowledgement(String topic) {
    final prefix = '$base/acks/';
    if (!topic.startsWith(prefix)) return null;
    final suffix = topic.substring(prefix.length);
    return suffix.isNotEmpty && !suffix.contains('/') ? suffix : null;
  }
}
