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
      scrollable: true,
      body: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: AgriMindSpacing.lg),
            const Center(child: AgriMindLogo(compact: true)),
            const SizedBox(height: AgriMindSpacing.xl),
            Text(
              'Configurez votre ferme',
              style: AgriMindTypography.heading2,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AgriMindSpacing.sm),
            Text(
              'Créons votre ferme pour commencer avec AgriMind. '
              'Un nom suffit pour cette première configuration.',
              style: AgriMindTypography.bodySecondary.copyWith(
                color: AgriMindColors.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AgriMindSpacing.xl),
            const _FarmVisual(),
            const SizedBox(height: AgriMindSpacing.xl),
            AgriMindCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  AgriMindTextField(
                    fieldKey: const Key('farm-name'),
                    controller: _nameController,
                    enabled: !creating,
                    label: 'Nom de la ferme',
                    leadingIcon: Icons.agriculture_outlined,
                    maxLength: 120,
                    textInputAction: TextInputAction.done,
                    validator: (value) =>
                        widget.controller.validateFarmName(value ?? ''),
                    onFieldSubmitted: (_) => _submit(),
                  ),
                  const SizedBox(height: AgriMindSpacing.lg),
                  AgriMindButton(
                    label: 'Créer ma ferme',
                    onPressed: _submit,
                    loading: creating,
                    icon: Icons.arrow_forward_rounded,
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

class _FarmVisual extends StatelessWidget {
  const _FarmVisual();

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Illustration décorative de ferme',
      image: true,
      child: Container(
        height: 112,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AgriMindColors.primaryContainer, AgriMindColors.sandBeige],
          ),
          borderRadius: BorderRadius.circular(AgriMindRadius.card),
          border: Border.all(color: AgriMindColors.outline),
        ),
        child: const ExcludeSemantics(
          child: Center(
            child: Icon(
              Icons.landscape_rounded,
              size: 64,
              color: AgriMindColors.primaryGreen,
            ),
          ),
        ),
      ),
    );
  }
}
