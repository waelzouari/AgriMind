import 'package:agrimind/core/design_system/design_system.dart';
import 'package:flutter/material.dart';

class AgriMindEmptyState extends StatelessWidget {
  const AgriMindEmptyState({
    required this.title,
    required this.message,
    this.icon = Icons.inbox_outlined,
    this.action,
    super.key,
  });

  final String title;
  final String message;
  final IconData icon;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          icon,
          size: AgriMindIconSizes.hero,
          color: AgriMindColors.textSecondary,
          semanticLabel: null,
        ),
        const SizedBox(height: AgriMindSpacing.md),
        Semantics(
          header: true,
          child: Text(
            title,
            style: AgriMindTypography.heading3,
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: AgriMindSpacing.xs),
        Text(
          message,
          style: AgriMindTypography.bodySecondary.copyWith(
            color: AgriMindColors.textSecondary,
          ),
          textAlign: TextAlign.center,
        ),
        if (action != null) ...[
          const SizedBox(height: AgriMindSpacing.lg),
          action!,
        ],
      ],
    );
  }
}
