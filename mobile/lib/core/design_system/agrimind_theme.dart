import 'package:agrimind/core/design_system/agrimind_colors.dart';
import 'package:agrimind/core/design_system/agrimind_component_sizes.dart';
import 'package:agrimind/core/design_system/agrimind_elevation.dart';
import 'package:agrimind/core/design_system/agrimind_radius.dart';
import 'package:agrimind/core/design_system/agrimind_spacing.dart';
import 'package:agrimind/core/design_system/agrimind_typography.dart';
import 'package:flutter/material.dart';

abstract final class AgriMindTheme {
  static ThemeData get light {
    const colorScheme = ColorScheme.light(
      primary: AgriMindColors.primaryGreen,
      onPrimary: AgriMindColors.onPrimary,
      secondary: AgriMindColors.earthBrown,
      onSecondary: AgriMindColors.onPrimary,
      error: AgriMindColors.error,
      onError: AgriMindColors.onPrimary,
      surface: AgriMindColors.surface,
      onSurface: AgriMindColors.textPrimary,
      outline: AgriMindColors.outline,
    );
    final radius = BorderRadius.circular(AgriMindRadius.medium);
    const minimumButtonSize = Size(
      AgriMindComponentSizes.minimumTouchTarget,
      AgriMindComponentSizes.buttonHeight,
    );
    const buttonPadding = EdgeInsets.symmetric(
      horizontal: AgriMindSpacing.xl,
      vertical: AgriMindSpacing.md,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: AgriMindColors.background,
      textTheme: AgriMindTypography.textTheme,
      appBarTheme: const AppBarTheme(
        backgroundColor: AgriMindColors.background,
        foregroundColor: AgriMindColors.textPrimary,
        centerTitle: false,
        elevation: AgriMindElevation.none,
        scrolledUnderElevation: AgriMindElevation.low,
      ),
      cardTheme: CardThemeData(
        color: AgriMindColors.surface,
        elevation: AgriMindElevation.low,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AgriMindRadius.large),
          side: const BorderSide(color: AgriMindColors.outline),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          minimumSize: minimumButtonSize,
          padding: buttonPadding,
          shape: RoundedRectangleBorder(borderRadius: radius),
          textStyle: AgriMindTypography.button,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: minimumButtonSize,
          padding: buttonPadding,
          shape: RoundedRectangleBorder(borderRadius: radius),
          textStyle: AgriMindTypography.button,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          minimumSize: const Size.square(
            AgriMindComponentSizes.minimumTouchTarget,
          ),
          shape: RoundedRectangleBorder(borderRadius: radius),
          textStyle: AgriMindTypography.button,
        ),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AgriMindColors.primaryGreen,
      ),
      focusColor: AgriMindColors.lightGreen,
    );
  }
}
