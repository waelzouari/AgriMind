import 'package:agrimind/core/design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('uses the approved light Material 3 theme', () {
    final theme = AgriMindTheme.light;

    expect(theme.useMaterial3, isTrue);
    expect(theme.brightness, Brightness.light);
    expect(theme.colorScheme.primary, AgriMindColors.primaryGreen);
    expect(theme.colorScheme.secondary, AgriMindColors.sandAccent);
    expect(theme.scaffoldBackgroundColor, AgriMindColors.background);
    expect(
      theme.textTheme.bodyLarge?.fontSize,
      AgriMindTypography.body.fontSize,
    );
    expect(theme.textTheme.bodyLarge?.height, AgriMindTypography.body.height);
    expect(theme.textTheme.bodyLarge?.color, AgriMindColors.textPrimary);
  });

  test('uses a light global system navigation bar with dark icons', () {
    const style = AgriMindTheme.systemUiOverlayStyle;

    expect(style.systemNavigationBarColor, AgriMindColors.background);
    expect(style.systemNavigationBarDividerColor, AgriMindColors.background);
    expect(style.systemNavigationBarIconBrightness, Brightness.dark);
    expect(style.systemNavigationBarContrastEnforced, isFalse);
    expect(AgriMindTheme.light.appBarTheme.systemOverlayStyle, style);
  });

  test('critical text and status combinations meet WCAG AA contrast', () {
    expect(
      _contrastRatio(AgriMindColors.primaryGreen, AgriMindColors.onPrimary),
      greaterThanOrEqualTo(4.5),
    );
    expect(
      _contrastRatio(AgriMindColors.success, AgriMindColors.successContainer),
      greaterThanOrEqualTo(4.5),
    );
    expect(
      _contrastRatio(AgriMindColors.warning, AgriMindColors.warningContainer),
      greaterThanOrEqualTo(4.5),
    );
    expect(
      _contrastRatio(AgriMindColors.error, AgriMindColors.errorContainer),
      greaterThanOrEqualTo(4.5),
    );
    expect(
      _contrastRatio(AgriMindColors.offline, AgriMindColors.offlineContainer),
      greaterThanOrEqualTo(4.5),
    );
    expect(
      _contrastRatio(AgriMindColors.info, AgriMindColors.infoContainer),
      greaterThanOrEqualTo(4.5),
    );
  });
}

double _contrastRatio(Color foreground, Color background) {
  final lighter = foreground.computeLuminance() > background.computeLuminance()
      ? foreground
      : background;
  final darker = lighter == foreground ? background : foreground;
  return (lighter.computeLuminance() + 0.05) /
      (darker.computeLuminance() + 0.05);
}
