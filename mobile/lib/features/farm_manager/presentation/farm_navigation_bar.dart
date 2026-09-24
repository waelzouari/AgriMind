import 'package:flutter/material.dart';

class FarmNavigationBar extends StatelessWidget {
  const FarmNavigationBar({
    required this.selectedIndex,
    required this.onHome,
    required this.onFarm,
    super.key,
  });

  final int selectedIndex;
  final VoidCallback onHome;
  final VoidCallback onFarm;

  @override
  Widget build(BuildContext context) => NavigationBar(
    selectedIndex: selectedIndex,
    onDestinationSelected: (index) => index == 0 ? onHome() : onFarm(),
    destinations: const [
      NavigationDestination(
        icon: Icon(Icons.home_outlined),
        selectedIcon: Icon(Icons.home_rounded),
        label: 'Accueil',
      ),
      NavigationDestination(
        icon: Icon(Icons.park_outlined),
        selectedIcon: Icon(Icons.park_rounded),
        label: 'Ferme',
      ),
    ],
  );
}
