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
      secondary: AgriMindColors.sandAccent,
      onSecondary: AgriMindColors.onPrimary,
      error: AgriMindColors.error,
      onError: AgriMindColors.onPrimary,
      surface: AgriMindColors.surface,
      onSurface: AgriMindColors.textPrimary,
      outline: AgriMindColors.outline,
      surfaceContainerHighest: AgriMindColors.surfaceMuted,
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
          borderRadius: BorderRadius.circular(AgriMindRadius.card),
          side: const BorderSide(color: AgriMindColors.outline),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AgriMindColors.primaryGreen,
          foregroundColor: AgriMindColors.onPrimary,
          disabledBackgroundColor: AgriMindColors.disabled,
          disabledForegroundColor: AgriMindColors.surface,
          elevation: AgriMindElevation.none,
          minimumSize: minimumButtonSize,
          padding: buttonPadding,
          shape: RoundedRectangleBorder(borderRadius: radius),
          textStyle: AgriMindTypography.button,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AgriMindColors.primaryDark,
          side: const BorderSide(color: AgriMindColors.primaryGreen),
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
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AgriMindColors.surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AgriMindSpacing.lg,
          vertical: AgriMindSpacing.md,
        ),
        border: OutlineInputBorder(
          borderRadius: radius,
          borderSide: const BorderSide(color: AgriMindColors.outline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: radius,
          borderSide: const BorderSide(color: AgriMindColors.outline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: radius,
          borderSide: const BorderSide(
            color: AgriMindColors.primaryGreen,
            width: 2,
          ),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: radius,
          borderSide: const BorderSide(color: AgriMindColors.error),
        ),
        prefixIconColor: AgriMindColors.primaryDark,
        labelStyle: AgriMindTypography.bodySecondary,
      ),
      focusColor: AgriMindColors.lightGreen,
    );
  }
}
