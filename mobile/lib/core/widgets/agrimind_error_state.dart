import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/widgets/agrimind_button.dart';
import 'package:flutter/material.dart';

class AgriMindErrorState extends StatelessWidget {
  const AgriMindErrorState({
    required this.title,
    required this.message,
    this.onRetry,
    this.retryLabel = 'Réessayer',
    super.key,
  });

  final String title;
  final String message;
  final VoidCallback? onRetry;
  final String retryLabel;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(
          Icons.error_outline_rounded,
          size: AgriMindIconSizes.hero,
          color: AgriMindColors.error,
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
        if (onRetry != null) ...[
          const SizedBox(height: AgriMindSpacing.lg),
          AgriMindButton(
            label: retryLabel,
            onPressed: onRetry,
            variant: AgriMindButtonVariant.secondary,
            icon: Icons.refresh_rounded,
          ),
        ],
      ],
    );
  }
}
