import 'package:flutter/material.dart';

class AgriMindTextField extends StatelessWidget {
  const AgriMindTextField({
    required this.controller,
    required this.label,
    this.fieldKey,
    this.leadingIcon,
    this.enabled = true,
    this.obscureText = false,
    this.keyboardType,
    this.textInputAction,
    this.autofillHints,
    this.maxLength,
    this.validator,
    this.onFieldSubmitted,
    super.key,
  });

  final Key? fieldKey;
  final TextEditingController controller;
  final String label;
  final IconData? leadingIcon;
  final bool enabled;
  final bool obscureText;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final Iterable<String>? autofillHints;
  final int? maxLength;
  final FormFieldValidator<String>? validator;
  final ValueChanged<String>? onFieldSubmitted;

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      key: fieldKey,
      controller: controller,
      enabled: enabled,
      obscureText: obscureText,
      keyboardType: keyboardType,
      textInputAction: textInputAction,
      autofillHints: autofillHints,
      maxLength: maxLength,
      validator: validator,
      onFieldSubmitted: onFieldSubmitted,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: leadingIcon == null ? null : Icon(leadingIcon),
      ),
    );
  }
}
