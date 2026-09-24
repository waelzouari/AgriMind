import 'package:agrimind/app/app_route.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/presentation/authentication_gate.dart';
import 'package:agrimind/features/dashboard/presentation/dashboard_session.dart';
import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:flutter/material.dart';

abstract final class AppRouter {
  static Route<void> onGenerateRoute(
    RouteSettings settings,
    AuthenticationController authentication,
    FarmController farmController,
    DashboardControllerFactory dashboardControllerFactory,
    WeatherControllerFactory weatherControllerFactory,
  ) {
    if (settings.name == AppRoute.signIn || settings.name == AppRoute.home) {
      return MaterialPageRoute<void>(
        settings: settings,
        builder: (_) => AuthenticationGate(
          controller: authentication,
          farmController: farmController,
          dashboardControllerFactory: dashboardControllerFactory,
          weatherControllerFactory: weatherControllerFactory,
        ),
      );
    }
    return MaterialPageRoute<void>(
      settings: settings,
      builder: (_) => AgriMindScaffold(
        title: 'Page introuvable',
        body: AgriMindErrorState(
          title: 'Route inconnue',
          message: 'La page demandée « ${settings.name ?? ''} » n’existe pas.',
        ),
      ),
    );
  }
}
