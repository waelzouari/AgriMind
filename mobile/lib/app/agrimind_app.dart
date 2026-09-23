import 'package:agrimind/app/app_route.dart';
import 'package:agrimind/app/app_router.dart';
import 'package:agrimind/core/config/app_config.dart';
import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:flutter/material.dart';

class AgriMindApp extends StatelessWidget {
  const AgriMindApp({required this.config, super.key});

  final AppConfig config;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: config.appName,
      debugShowCheckedModeBanner: false,
      theme: AgriMindTheme.light,
      initialRoute: AppRoute.foundation,
      onGenerateRoute: AppRouter.onGenerateRoute,
    );
  }
}
