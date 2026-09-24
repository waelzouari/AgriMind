import 'package:agrimind/features/farm_manager/domain/tree_position.dart';

final class FarmTree {
  const FarmTree({
    required this.id,
    required this.farmId,
    required this.label,
    required this.position,
  });

  final String id;
  final String farmId;
  final String label;
  final TreePosition position;
}
