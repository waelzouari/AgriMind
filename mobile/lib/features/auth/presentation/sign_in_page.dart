import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:flutter/material.dart';

class SignInPage extends StatefulWidget {
  const SignInPage({required this.controller, super.key});

  final AuthenticationController controller;

  @override
  State<SignInPage> createState() => _SignInPageState();
}

class _SignInPageState extends State<SignInPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (widget.controller.isSubmitting || !_formKey.currentState!.validate()) {
      return;
    }
    await widget.controller.signIn(
      email: _emailController.text.trim(),
      password: _passwordController.text,
    );
  }

  @override
  Widget build(BuildContext context) {
    return AgriMindScaffold(
      scrollable: true,
      body: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const AgriMindLandscape(height: 260, child: AgriMindLogo()),
            const SizedBox(height: AgriMindSpacing.lg),
            AgriMindCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Semantics(
                    header: true,
                    child: Text(
                      'Bon retour',
                      style: AgriMindTypography.heading2,
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: AgriMindSpacing.xs),
                  Text(
                    'Connectez-vous à votre compte AgriMind.',
                    style: AgriMindTypography.bodySecondary.copyWith(
                      color: AgriMindColors.textSecondary,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: AgriMindSpacing.xl),
                  AgriMindTextField(
                    fieldKey: const Key('sign-in-email'),
                    controller: _emailController,
                    enabled: !widget.controller.isSubmitting,
                    label: 'Adresse e-mail',
                    leadingIcon: Icons.email_outlined,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    validator: (value) {
                      final email = value?.trim() ?? '';
                      if (!RegExp(
                        r'^[^@\s]+@[^@\s]+\.[^@\s]+$',
                      ).hasMatch(email)) {
                        return 'Saisissez une adresse e-mail valide.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: AgriMindSpacing.lg),
                  AgriMindTextField(
                    fieldKey: const Key('sign-in-password'),
                    controller: _passwordController,
                    enabled: !widget.controller.isSubmitting,
                    label: 'Mot de passe',
                    leadingIcon: Icons.lock_outline_rounded,
                    obscureText: true,
                    autofillHints: const [AutofillHints.password],
                    validator: (value) => (value == null || value.isEmpty)
                        ? 'Saisissez votre mot de passe.'
                        : null,
                    onFieldSubmitted: (_) => _submit(),
                  ),
                  if (widget.controller.errorMessage case final message?) ...[
                    const SizedBox(height: AgriMindSpacing.lg),
                    Semantics(
                      liveRegion: true,
                      child: Text(
                        message,
                        key: const Key('sign-in-error'),
                        style: AgriMindTypography.bodySecondary.copyWith(
                          color: AgriMindColors.error,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                  const SizedBox(height: AgriMindSpacing.xl),
                  AgriMindButton(
                    label: 'Se connecter',
                    onPressed: _submit,
                    loading: widget.controller.isSubmitting,
                    icon: Icons.arrow_forward_rounded,
                  ),
                ],
              ),
            ),
            const SizedBox(height: AgriMindSpacing.lg),
            const AgriMindLandscape(height: 96),
          ],
        ),
      ),
    );
  }
}
