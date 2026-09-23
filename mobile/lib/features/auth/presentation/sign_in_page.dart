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
            const SizedBox(height: AgriMindSpacing.xxxl),
            Semantics(
              header: true,
              child: Text(
                'AGRIMIND',
                style: AgriMindTypography.heading1,
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: AgriMindSpacing.sm),
            Text(
              'Connectez-vous pour accéder à votre espace agricole.',
              style: AgriMindTypography.bodySecondary,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AgriMindSpacing.xxl),
            AgriMindCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TextFormField(
                    key: const Key('sign-in-email'),
                    controller: _emailController,
                    enabled: !widget.controller.isSubmitting,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    decoration: const InputDecoration(
                      labelText: 'Adresse e-mail',
                      prefixIcon: Icon(Icons.email_outlined),
                    ),
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
                  TextFormField(
                    key: const Key('sign-in-password'),
                    controller: _passwordController,
                    enabled: !widget.controller.isSubmitting,
                    obscureText: true,
                    autofillHints: const [AutofillHints.password],
                    decoration: const InputDecoration(
                      labelText: 'Mot de passe',
                      prefixIcon: Icon(Icons.lock_outline_rounded),
                    ),
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
