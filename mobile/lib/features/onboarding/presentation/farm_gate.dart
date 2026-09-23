import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/presentation/authenticated_home_page.dart';
import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:agrimind/features/onboarding/presentation/farm_onboarding_page.dart';
import 'package:flutter/material.dart';

class FarmGate extends StatelessWidget {
  const FarmGate({
    required this.authentication,
    required this.farmController,
    super.key,
  });

  final AuthenticationController authentication;
  final FarmController farmController;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: farmController,
      builder: (context, _) => switch (farmController.status) {
        FarmStatus.idle || FarmStatus.checking => const AgriMindScaffold(
          body: Center(
            child: AgriMindLoadingIndicator(
              label: 'Vérification de votre ferme',
            ),
          ),
        ),
        FarmStatus.noFarm ||
        FarmStatus.creating => FarmOnboardingPage(controller: farmController),
        FarmStatus.configured => AuthenticatedHomePage(
          controller: authentication,
          farm: farmController.farm!,
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
