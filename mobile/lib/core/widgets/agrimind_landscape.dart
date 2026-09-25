import 'package:agrimind/core/design_system/design_system.dart';
import 'package:flutter/material.dart';

class AgriMindLandscape extends StatelessWidget {
  const AgriMindLandscape({this.height = 180, this.child, super.key});

  final double height;
  final Widget? child;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: height,
    child: ClipRRect(
      borderRadius: BorderRadius.circular(AgriMindRadius.card),
      child: CustomPaint(
        painter: const _LandscapePainter(),
        child: Center(child: child),
      ),
    ),
  );
}

class _LandscapePainter extends CustomPainter {
  const _LandscapePainter();

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = AgriMindColors.backgroundSoft,
    );
    _hill(
      canvas,
      size,
      size.height * .40,
      AgriMindColors.primaryContainer,
      .18,
    );
    _hill(canvas, size, size.height * .58, AgriMindColors.sandBeige, .28);
    _hill(canvas, size, size.height * .72, AgriMindColors.decorativeGreen, .34);
    _hill(canvas, size, size.height * .84, AgriMindColors.sandAccent, .20);
    final plant = Paint()..color = AgriMindColors.primaryGreen;
    canvas.drawRect(
      Rect.fromLTWH(size.width * .12, size.height * .66, 3, size.height * .2),
      plant,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.width * .09, size.height * .69),
        width: 28,
        height: 15,
      ),
      plant,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(size.width * .15, size.height * .73),
        width: 28,
        height: 15,
      ),
      plant,
    );
  }

  void _hill(Canvas canvas, Size size, double top, Color color, double bend) {
    final path = Path()
      ..moveTo(0, top)
      ..quadraticBezierTo(
        size.width * bend,
        top - size.height * .22,
        size.width * .52,
        top,
      )
      ..quadraticBezierTo(
        size.width * .82,
        top + size.height * .12,
        size.width,
        top - size.height * .08,
      )
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(path, Paint()..color = color);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
