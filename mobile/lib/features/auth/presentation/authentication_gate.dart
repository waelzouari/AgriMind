import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/presentation/sign_in_page.dart';
import 'package:agrimind/features/dashboard/presentation/dashboard_session.dart';
import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:agrimind/features/onboarding/presentation/farm_gate.dart';
import 'package:flutter/material.dart';

class AuthenticationGate extends StatelessWidget {
  const AuthenticationGate({
    required this.controller,
    required this.farmController,
    required this.dashboardControllerFactory,
    required this.weatherControllerFactory,
    super.key,
  });

  final AuthenticationController controller;
  final FarmController farmController;
  final DashboardControllerFactory dashboardControllerFactory;
  final WeatherControllerFactory weatherControllerFactory;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) => switch (controller.status) {
        AuthenticationStatus.restoring => const AgriMindScaffold(
          body: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AgriMindLogo(),
                SizedBox(height: AgriMindSpacing.xl),
                AgriMindLoadingIndicator(label: 'Restauration de la session'),
              ],
            ),
          ),
        ),
        AuthenticationStatus.unauthenticated => SignInPage(
          controller: controller,
        ),
        AuthenticationStatus.authenticated => FarmGate(
          authentication: controller,
          farmController: farmController,
          dashboardControllerFactory: dashboardControllerFactory,
          weatherControllerFactory: weatherControllerFactory,
        ),
      },
    );
  }
}
