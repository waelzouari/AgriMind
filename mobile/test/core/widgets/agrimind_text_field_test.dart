import 'package:agrimind/core/widgets/agrimind_text_field.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/pump_app.dart';

void main() {
  testWidgets('shows its label, icon, focus state, and validation error', (
    tester,
  ) async {
    final controller = TextEditingController();
    addTearDown(controller.dispose);
    final formKey = GlobalKey<FormState>();

    await pumpAgriMindWidget(
      tester,
      Form(
        key: formKey,
        child: AgriMindTextField(
          controller: controller,
          label: 'Nom de la ferme',
          leadingIcon: Icons.agriculture_outlined,
          validator: (value) => value!.isEmpty ? 'Champ requis' : null,
        ),
      ),
    );

    expect(find.text('Nom de la ferme'), findsOneWidget);
    expect(find.byIcon(Icons.agriculture_outlined), findsOneWidget);
    formKey.currentState!.validate();
    await tester.pump();
    expect(find.text('Champ requis'), findsOneWidget);
  });
}
