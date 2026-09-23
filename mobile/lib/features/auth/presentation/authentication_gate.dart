import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/presentation/sign_in_page.dart';
import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:agrimind/features/onboarding/presentation/farm_gate.dart';
import 'package:flutter/material.dart';

class AuthenticationGate extends StatelessWidget {
  const AuthenticationGate({
    required this.controller,
    required this.farmController,
    super.key,
  });

  final AuthenticationController controller;
  final FarmController farmController;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) => switch (controller.status) {
        AuthenticationStatus.restoring => const AgriMindScaffold(
          body: Center(
            child: AgriMindLoadingIndicator(
              label: 'Restauration de la session',
            ),
          ),
        ),
        AuthenticationStatus.unauthenticated => SignInPage(
          controller: controller,
        ),
        AuthenticationStatus.authenticated => FarmGate(
          authentication: controller,
          farmController: farmController,
        ),
      },
    );
  }
}
