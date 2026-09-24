enum FarmManagerFailureType { unauthorized, unavailable, invalidData, unknown }

final class FarmManagerFailure implements Exception {
  const FarmManagerFailure(this.type);

  final FarmManagerFailureType type;
}
