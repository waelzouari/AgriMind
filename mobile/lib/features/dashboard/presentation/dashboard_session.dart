import 'dart:async';

import 'package:agrimind/features/auth/application/authentication_controller.dart';
import 'package:agrimind/features/dashboard/application/dashboard_controller.dart';
import 'package:agrimind/features/dashboard/presentation/realtime_dashboard_page.dart';
import 'package:agrimind/features/onboarding/domain/farm.dart';
import 'package:agrimind/features/weather/application/weather_controller.dart';
import 'package:flutter/widgets.dart';

typedef DashboardControllerFactory = DashboardController Function();
typedef WeatherControllerFactory = WeatherController Function();

class DashboardSession extends StatefulWidget {
  const DashboardSession({
    required this.authentication,
    required this.farm,
    required this.controllerFactory,
    required this.weatherControllerFactory,
    super.key,
  });
  final AuthenticationController authentication;
  final Farm farm;
  final DashboardControllerFactory controllerFactory;
  final WeatherControllerFactory weatherControllerFactory;

  @override
  State<DashboardSession> createState() => _DashboardSessionState();
}

class _DashboardSessionState extends State<DashboardSession> {
  late DashboardController _controller;
  late WeatherController _weatherController;

  @override
  void initState() {
    super.initState();
    _start();
  }

  void _start() {
    _controller = widget.controllerFactory();
    _weatherController = widget.weatherControllerFactory();
    unawaited(
      _controller.start(
        widget.farm.id,
        requestedBy: widget.authentication.session!.userId,
      ),
    );
    unawaited(_weatherController.load(widget.farm));
  }

  @override
  void didUpdateWidget(covariant DashboardSession oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.farm.id != widget.farm.id) {
      _controller.dispose();
      _weatherController.dispose();
      _start();
    } else if (oldWidget.farm.latitude != widget.farm.latitude ||
        oldWidget.farm.longitude != widget.farm.longitude) {
      unawaited(_weatherController.load(widget.farm));
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _weatherController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => RealtimeDashboardPage(
    authentication: widget.authentication,
    farm: widget.farm,
    controller: _controller,
    weatherController: _weatherController,
  );
}
