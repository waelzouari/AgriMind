import 'package:agrimind/core/design_system/design_system.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('spacing and radius scales remain ordered', () {
    expect([
      AgriMindSpacing.xxs,
      AgriMindSpacing.xs,
      AgriMindSpacing.sm,
      AgriMindSpacing.md,
      AgriMindSpacing.lg,
      AgriMindSpacing.xl,
      AgriMindSpacing.xxl,
      AgriMindSpacing.xxxl,
    ], orderedEquals([2, 4, 8, 12, 16, 24, 32, 48]));
    expect(AgriMindRadius.small, lessThan(AgriMindRadius.medium));
    expect(AgriMindRadius.medium, lessThan(AgriMindRadius.large));
    expect(AgriMindRadius.large, lessThan(AgriMindRadius.extraLarge));
  });

  test('interactive component tokens meet the minimum touch target', () {
    expect(AgriMindComponentSizes.minimumTouchTarget, greaterThanOrEqualTo(48));
    expect(AgriMindComponentSizes.buttonHeight, greaterThanOrEqualTo(48));
    expect(AgriMindComponentSizes.iconButton, greaterThanOrEqualTo(48));
  });
}
