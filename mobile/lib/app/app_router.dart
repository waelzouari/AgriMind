import 'package:agrimind/app/app_route.dart';
import 'package:agrimind/core/pages/foundation_showcase_page.dart';
import 'package:agrimind/core/widgets/widgets.dart';
import 'package:flutter/material.dart';

abstract final class AppRouter {
  static Route<void> onGenerateRoute(RouteSettings settings) {
    if (settings.name == AppRoute.foundation) {
      return MaterialPageRoute<void>(
        settings: settings,
        builder: (_) => const FoundationShowcasePage(),
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
