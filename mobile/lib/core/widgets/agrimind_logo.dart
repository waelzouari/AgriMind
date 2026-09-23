import 'package:agrimind/core/assets/agrimind_assets.dart';
import 'package:agrimind/core/design_system/design_system.dart';
import 'package:flutter/material.dart';

class AgriMindLogo extends StatelessWidget {
  const AgriMindLogo({this.compact = false, super.key});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      image: true,
      label: 'AgriMind',
      child: ExcludeSemantics(
        child: Image.asset(
          AgriMindAssets.logo,
          width: compact
              ? AgriMindComponentSizes.logoCompactWidth
              : AgriMindComponentSizes.logoWidth,
          fit: BoxFit.contain,
          filterQuality: FilterQuality.high,
        ),
      ),
    );
  }
}
