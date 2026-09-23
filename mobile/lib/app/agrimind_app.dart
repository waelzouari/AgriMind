import 'dart:async';

import 'package:agrimind/app/app_router.dart';
import 'package:agrimind/core/config/app_config.dart';
import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/presentation/authentication_gate.dart';
import 'package:agrimind/features/onboarding/application/farm_controller.dart';
import 'package:flutter/material.dart';

class AgriMindApp extends StatefulWidget {
  const AgriMindApp({
    required this.config,
    required this.authentication,
    required this.farmController,
    super.key,
  });

  final AppConfig config;
  final AuthenticationController authentication;
  final FarmController farmController;

  @override
  State<AgriMindApp> createState() => _AgriMindAppState();
}

class _AgriMindAppState extends State<AgriMindApp> {
  @override
  void initState() {
    super.initState();
    widget.authentication.addListener(_synchronizeFarm);
    unawaited(widget.authentication.restoreSession());
  }

  void _synchronizeFarm() {
    unawaited(
      widget.farmController.synchronizeAuthenticatedUser(
        widget.authentication.session?.userId,
      ),
    );
  }

  @override
  void dispose() {
    widget.authentication.removeListener(_synchronizeFarm);
    widget.farmController.dispose();
    widget.authentication.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: widget.config.appName,
      debugShowCheckedModeBanner: false,
      theme: AgriMindTheme.light,
      home: AuthenticationGate(
        controller: widget.authentication,
        farmController: widget.farmController,
      ),
      onGenerateRoute: (settings) => AppRouter.onGenerateRoute(
        settings,
        widget.authentication,
        widget.farmController,
      ),
    );
  }
}
