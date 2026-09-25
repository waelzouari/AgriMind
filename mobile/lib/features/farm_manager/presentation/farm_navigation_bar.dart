import 'package:flutter/material.dart';

class FarmNavigationBar extends StatelessWidget {
  const FarmNavigationBar({
    required this.selectedIndex,
    required this.onHome,
    required this.onFarm,
    this.onHistory,
    super.key,
  });

  final int selectedIndex;
  final VoidCallback onHome;
  final VoidCallback onFarm;
  final VoidCallback? onHistory;

  @override
  Widget build(BuildContext context) => NavigationBar(
    selectedIndex: selectedIndex,
    onDestinationSelected: (index) => switch (index) {
      0 => onHome(),
      1 => onFarm(),
      _ => onHistory?.call(),
    },
    destinations: [
      NavigationDestination(
        icon: Icon(Icons.home_outlined),
        selectedIcon: Icon(Icons.home_rounded),
        label: 'Accueil',
      ),
      if (onHistory != null)
        const NavigationDestination(
          icon: Icon(Icons.history_outlined),
          selectedIcon: Icon(Icons.history_rounded),
          label: 'Historique',
        ),
      NavigationDestination(
        icon: Icon(Icons.park_outlined),
        selectedIcon: Icon(Icons.park_rounded),
        label: 'Ferme',
      ),
    ],
  );
}
