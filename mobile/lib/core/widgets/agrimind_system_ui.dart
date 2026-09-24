import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

class AgriMindSystemUi extends StatelessWidget {
  const AgriMindSystemUi({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) => AnnotatedRegion<SystemUiOverlayStyle>(
    value: AgriMindTheme.systemUiOverlayStyle,
    child: child,
  );
}
