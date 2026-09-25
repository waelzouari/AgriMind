import 'package:agrimind/core/design_system/agrimind_colors.dart';
import 'package:agrimind/core/design_system/agrimind_component_sizes.dart';
import 'package:agrimind/core/design_system/agrimind_elevation.dart';
import 'package:agrimind/core/design_system/agrimind_radius.dart';
import 'package:agrimind/core/design_system/agrimind_spacing.dart';
import 'package:agrimind/core/design_system/agrimind_typography.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

abstract final class AgriMindTheme {
  static const systemUiOverlayStyle = SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarBrightness: Brightness.light,
    statusBarIconBrightness: Brightness.dark,
    systemNavigationBarColor: AgriMindColors.background,
    systemNavigationBarDividerColor: AgriMindColors.background,
    systemNavigationBarIconBrightness: Brightness.dark,
    systemNavigationBarContrastEnforced: false,
  );

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
        systemOverlayStyle: systemUiOverlayStyle,
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
      navigationBarTheme: NavigationBarThemeData(
        height: 68,
        elevation: AgriMindElevation.low,
        backgroundColor: AgriMindColors.surface,
        indicatorColor: AgriMindColors.navigationSelected,
        indicatorShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AgriMindRadius.pill),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected)
                ? AgriMindColors.primaryGreen
                : AgriMindColors.textSecondary,
          ),
        ),
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => AgriMindTypography.caption.copyWith(
            color: states.contains(WidgetState.selected)
                ? AgriMindColors.primaryDark
                : AgriMindColors.textSecondary,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w700
                : FontWeight.w500,
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: AgriMindColors.surface,
        selectedColor: AgriMindColors.primaryGreen,
        side: const BorderSide(color: AgriMindColors.outline),
        shape: RoundedRectangleBorder(borderRadius: radius),
        labelStyle: AgriMindTypography.caption,
        secondaryLabelStyle: AgriMindTypography.caption.copyWith(
          color: AgriMindColors.onPrimary,
          fontWeight: FontWeight.w700,
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
