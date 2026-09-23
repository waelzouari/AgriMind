import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> pumpAgriMindWidget(
  WidgetTester tester,
  Widget child, {
  Size size = const Size(390, 844),
  double textScaleFactor = 1,
}) async {
  await tester.binding.setSurfaceSize(size);
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      theme: AgriMindTheme.light,
      home: MediaQuery(
        data: MediaQueryData(textScaler: TextScaler.linear(textScaleFactor)),
        child: Scaffold(body: Center(child: child)),
      ),
    ),
  );
  await tester.pump();
}
