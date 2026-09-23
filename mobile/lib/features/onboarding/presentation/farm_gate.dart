import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/dashboard/presentation/dashboard_session.dart';
import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:agrimind/features/onboarding/presentation/farm_onboarding_page.dart';
import 'package:flutter/material.dart';

class FarmGate extends StatelessWidget {
  const FarmGate({
    required this.authentication,
    required this.farmController,
    required this.dashboardControllerFactory,
    super.key,
  });

  final AuthenticationController authentication;
  final FarmController farmController;
  final DashboardControllerFactory dashboardControllerFactory;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: farmController,
      builder: (context, _) => switch (farmController.status) {
        FarmStatus.idle || FarmStatus.checking => const AgriMindScaffold(
          body: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AgriMindLogo(),
                SizedBox(height: AgriMindSpacing.xl),
                AgriMindLoadingIndicator(label: 'Vérification de votre ferme'),
              ],
            ),
          ),
        ),
        FarmStatus.noFarm ||
        FarmStatus.creating => FarmOnboardingPage(controller: farmController),
        FarmStatus.configured => DashboardSession(
          authentication: authentication,
          farm: farmController.farm!,
          controllerFactory: dashboardControllerFactory,
        ),
        FarmStatus.failure => AgriMindScaffold(
          body: Center(
            child: AgriMindErrorState(
              title: 'Ferme indisponible',
              message:
                  farmController.errorMessage ??
                  'La ferme ne peut pas être chargée.',
              onRetry: farmController.retry,
            ),
          ),
        ),
      },
    );
  }
}
