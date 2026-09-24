final class TreePosition implements Comparable<TreePosition> {
  const TreePosition({required this.row, required this.column})
    : assert(row >= 1 && row <= 26),
      assert(column >= 1 && column <= 99);

  final int row;
  final int column;

  String get displayLabel => '${String.fromCharCode(64 + row)}$column';

  @override
  int compareTo(TreePosition other) {
    final rowComparison = row.compareTo(other.row);
    return rowComparison != 0 ? rowComparison : column.compareTo(other.column);
  }

  @override
  bool operator ==(Object other) =>
      other is TreePosition && row == other.row && column == other.column;

  @override
  int get hashCode => Object.hash(row, column);
}
