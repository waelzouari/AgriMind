import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/models/ui_status.dart';
import 'package:flutter/material.dart';

class AgriMindStatusBadge extends StatelessWidget {
  const AgriMindStatusBadge({
    required this.status,
    this.labelOverride,
    this.semanticLabel,
    super.key,
  });

  final UiStatus status;
  final String? labelOverride;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final label = labelOverride ?? status.label;
    return Semantics(
      label: semanticLabel ?? 'État : $label',
      container: true,
      excludeSemantics: true,
      child: Container(
        constraints: const BoxConstraints(
          minHeight: AgriMindComponentSizes.statusBadgeMinHeight,
        ),
        padding: const EdgeInsets.symmetric(
          horizontal: AgriMindSpacing.md,
          vertical: AgriMindSpacing.xs,
        ),
        decoration: BoxDecoration(
          color: status.backgroundColor,
          borderRadius: BorderRadius.circular(AgriMindRadius.pill),
        ),
        child: Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: AgriMindSpacing.xs,
          children: [
            Icon(
              status.icon,
              size: AgriMindIconSizes.small,
              color: status.foregroundColor,
            ),
            Text(
              label,
              style: AgriMindTypography.label.copyWith(
                color: status.foregroundColor,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
