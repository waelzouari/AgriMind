import 'package:agrimind/core/design_system/design_system.dart';
import 'package:flutter/material.dart';

class AgriMindLoadingIndicator extends StatelessWidget {
  const AgriMindLoadingIndicator({
    this.label = 'Chargement en cours',
    this.compact = false,
    super.key,
  });

  final String label;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    const indicator = SizedBox.square(
      dimension: AgriMindComponentSizes.loadingIndicator,
      child: CircularProgressIndicator(strokeWidth: AgriMindSpacing.xxs),
    );
    return Semantics(
      label: label,
      liveRegion: true,
      excludeSemantics: true,
      child: compact
          ? indicator
          : Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                indicator,
                const SizedBox(height: AgriMindSpacing.md),
                Text(label, textAlign: TextAlign.center),
              ],
            ),
    );
  }
}
