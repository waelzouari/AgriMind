import 'package:agrimind/core/design_system/design_system.dart';
import 'package:flutter/material.dart';

class AgriMindCard extends StatelessWidget {
  const AgriMindCard({
    required this.child,
    this.padding = const EdgeInsets.all(AgriMindSpacing.md),
    this.onTap,
    this.semanticLabel,
    this.backgroundColor,
    super.key,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final String? semanticLabel;
  final Color? backgroundColor;

  @override
  Widget build(BuildContext context) {
    final content = ConstrainedBox(
      constraints: const BoxConstraints(
        minHeight: AgriMindComponentSizes.cardMinHeight,
      ),
      child: Padding(padding: padding, child: child),
    );
    final card = Card(
      color: backgroundColor,
      clipBehavior: Clip.antiAlias,
      child: onTap == null ? content : InkWell(onTap: onTap, child: content),
    );
    if (semanticLabel == null) return card;
    return Semantics(label: semanticLabel, button: onTap != null, child: card);
  }
}
