import 'package:agrimind/core/design_system/agrimind_colors.dart';
import 'package:flutter/material.dart';

abstract final class AgriMindTypography {
  static const display = TextStyle(
    fontSize: 40,
    height: 1.2,
    fontWeight: FontWeight.w700,
  );
  static const heading1 = TextStyle(
    fontSize: 32,
    height: 1.25,
    fontWeight: FontWeight.w700,
  );
  static const heading2 = TextStyle(
    fontSize: 24,
    height: 1.33,
    fontWeight: FontWeight.w700,
  );
  static const heading3 = TextStyle(
    fontSize: 20,
    height: 1.4,
    fontWeight: FontWeight.w600,
  );
  static const cardTitle = TextStyle(
    fontSize: 16,
    height: 1.35,
    fontWeight: FontWeight.w600,
  );
  static const body = TextStyle(fontSize: 16, height: 1.5);
  static const bodySecondary = TextStyle(fontSize: 14, height: 1.43);
  static const caption = TextStyle(fontSize: 12, height: 1.33);
  static const button = TextStyle(
    fontSize: 16,
    height: 1.25,
    fontWeight: FontWeight.w600,
  );
  static const label = TextStyle(
    fontSize: 14,
    height: 1.43,
    fontWeight: FontWeight.w600,
  );
  static const metricValue = TextStyle(
    fontSize: 32,
    height: 1.11,
    fontWeight: FontWeight.w700,
  );
  static const sensorValue = metricValue;

  static final textTheme =
      const TextTheme(
        displayLarge: display,
        headlineLarge: heading1,
        headlineMedium: heading2,
        headlineSmall: heading3,
        bodyLarge: body,
        bodyMedium: bodySecondary,
        bodySmall: caption,
        labelLarge: button,
        labelMedium: label,
      ).apply(
        bodyColor: AgriMindColors.textPrimary,
        displayColor: AgriMindColors.textPrimary,
      );
}
