import 'package:agrimind/core/design_system/design_system.dart';
import 'package:flutter/material.dart';

class AgriMindSectionHeader extends StatelessWidget {
  const AgriMindSectionHeader({
    required this.title,
    this.subtitle,
    this.action,
    super.key,
  });

  final String title;
  final String? subtitle;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(
                header: true,
                child: Text(title, style: AgriMindTypography.heading3),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: AgriMindSpacing.xs),
                Text(
                  subtitle!,
                  style: AgriMindTypography.bodySecondary.copyWith(
                    color: AgriMindColors.textSecondary,
                  ),
                ),
              ],
            ],
          ),
        ),
        if (action != null) ...[
          const SizedBox(width: AgriMindSpacing.sm),
          action!,
        ],
      ],
    );
  }
}
