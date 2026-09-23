import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/presentation/authenticated_home_page.dart';
import 'package:agrimind/features/auth/presentation/sign_in_page.dart';
import 'package:flutter/material.dart';

class AuthenticationGate extends StatelessWidget {
  const AuthenticationGate({required this.controller, super.key});

  final AuthenticationController controller;

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
        AuthenticationStatus.authenticated => AuthenticatedHomePage(
          controller: controller,
        ),
      },
    );
  }
}
