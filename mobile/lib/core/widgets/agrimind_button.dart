import 'package:agrimind/core/design_system/design_system.dart';
import 'package:flutter/material.dart';

enum AgriMindButtonVariant { primary, secondary, text }

class AgriMindButton extends StatelessWidget {
  const AgriMindButton({
    required this.label,
    required this.onPressed,
    this.variant = AgriMindButtonVariant.primary,
    this.icon,
    this.loading = false,
    this.semanticLabel,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;
  final AgriMindButtonVariant variant;
  final IconData? icon;
  final bool loading;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final effectiveOnPressed = loading ? null : onPressed;
    final child = loading
        ? const SizedBox.square(
            dimension: AgriMindComponentSizes.loadingIndicator,
            child: CircularProgressIndicator(strokeWidth: AgriMindSpacing.xxs),
          )
        : _ButtonContent(label: label, icon: icon);
    final button = switch (variant) {
      AgriMindButtonVariant.primary => ElevatedButton(
        onPressed: effectiveOnPressed,
        child: child,
      ),
      AgriMindButtonVariant.secondary => OutlinedButton(
        onPressed: effectiveOnPressed,
        child: child,
      ),
      AgriMindButtonVariant.text => TextButton(
        onPressed: effectiveOnPressed,
        child: child,
      ),
    };
    return Semantics(
      label: semanticLabel ?? label,
      button: true,
      enabled: effectiveOnPressed != null,
      value: loading ? 'Chargement' : null,
      excludeSemantics: true,
      child: button,
    );
  }
}

class _ButtonContent extends StatelessWidget {
  const _ButtonContent({required this.label, this.icon});

  final String label;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    if (icon == null) return Text(label, textAlign: TextAlign.center);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: AgriMindIconSizes.medium),
        const SizedBox(width: AgriMindSpacing.sm),
        Flexible(child: Text(label, textAlign: TextAlign.center)),
      ],
    );
  }
}
