import 'dart:async';

import 'package:agrimind/app/app_router.dart';
import 'package:agrimind/core/config/app_config.dart';
import 'package:agrimind/core/design_system/agrimind_theme.dart';
import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/auth/presentation/authentication_gate.dart';
import 'package:flutter/material.dart';

class AgriMindApp extends StatefulWidget {
  const AgriMindApp({
    required this.config,
    required this.authentication,
    super.key,
  });

  final AppConfig config;
  final AuthenticationController authentication;

  @override
  State<AgriMindApp> createState() => _AgriMindAppState();
}

class _AgriMindAppState extends State<AgriMindApp> {
  @override
  void initState() {
    super.initState();
    unawaited(widget.authentication.restoreSession());
  }

  @override
  void dispose() {
    widget.authentication.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: widget.config.appName,
      debugShowCheckedModeBanner: false,
      theme: AgriMindTheme.light,
      home: AuthenticationGate(controller: widget.authentication),
      onGenerateRoute: (settings) =>
          AppRouter.onGenerateRoute(settings, widget.authentication),
    );
  }
}
