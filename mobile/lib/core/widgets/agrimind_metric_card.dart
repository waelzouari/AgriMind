import 'package:agrimind/core/design_system/design_system.dart';
import 'package:agrimind/core/widgets/agrimind_card.dart';
import 'package:flutter/material.dart';

class AgriMindMetricCard extends StatelessWidget {
  const AgriMindMetricCard({
    required this.icon,
    required this.label,
    required this.value,
    this.unit,
    this.status,
    this.trailing,
    super.key,
  });

  final IconData icon;
  final String label;
  final String value;
  final String? unit;
  final Widget? status;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return AgriMindCard(
      semanticLabel: '$label : $value${unit == null ? '' : ' $unit'}',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              DecoratedBox(
                decoration: const BoxDecoration(
                  color: AgriMindColors.primaryContainer,
                  shape: BoxShape.circle,
                ),
                child: Padding(
                  padding: const EdgeInsets.all(AgriMindSpacing.sm),
                  child: Icon(icon, color: AgriMindColors.primaryDark),
                ),
              ),
              const SizedBox(width: AgriMindSpacing.sm),
              Expanded(child: Text(label, style: AgriMindTypography.cardTitle)),
              ?trailing,
            ],
          ),
          const SizedBox(height: AgriMindSpacing.md),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(value, style: AgriMindTypography.metricValue),
              if (unit != null) ...[
                const SizedBox(width: AgriMindSpacing.xs),
                Padding(
                  padding: const EdgeInsets.only(bottom: AgriMindSpacing.xs),
                  child: Text(unit!, style: AgriMindTypography.label),
                ),
              ],
            ],
          ),
          if (status != null) ...[
            const SizedBox(height: AgriMindSpacing.sm),
            status!,
          ],
        ],
      ),
    );
  }
}
