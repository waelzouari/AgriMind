import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:flutter/material.dart';

class FarmOnboardingPage extends StatefulWidget {
  const FarmOnboardingPage({required this.controller, super.key});

  final FarmController controller;

  @override
  State<FarmOnboardingPage> createState() => _FarmOnboardingPageState();
}

class _FarmOnboardingPageState extends State<FarmOnboardingPage> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(
      text: widget.controller.pendingFarmName,
    );
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (widget.controller.status == FarmStatus.creating ||
        !_formKey.currentState!.validate()) {
      return;
    }
    await widget.controller.createFarm(_nameController.text);
  }

  @override
  Widget build(BuildContext context) {
    final creating = widget.controller.status == FarmStatus.creating;
    return AgriMindScaffold(
      title: 'AGRIMIND',
      scrollable: true,
      body: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Configurez votre ferme', style: AgriMindTypography.heading2),
            const SizedBox(height: AgriMindSpacing.sm),
            Text(
              'Un nom suffit pour commencer. Les réglages agricoles seront '
              'ajoutés dans leurs fonctionnalités dédiées.',
              style: AgriMindTypography.bodySecondary,
            ),
            const SizedBox(height: AgriMindSpacing.xl),
            AgriMindCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TextFormField(
                    key: const Key('farm-name'),
                    controller: _nameController,
                    enabled: !creating,
                    maxLength: 120,
                    textInputAction: TextInputAction.done,
                    decoration: const InputDecoration(
                      labelText: 'Nom de la ferme',
                      prefixIcon: Icon(Icons.agriculture_outlined),
                    ),
                    validator: (value) =>
                        widget.controller.validateFarmName(value ?? ''),
                    onFieldSubmitted: (_) => _submit(),
                  ),
                  const SizedBox(height: AgriMindSpacing.lg),
                  AgriMindButton(
                    label: 'Créer ma ferme',
                    onPressed: _submit,
                    loading: creating,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
