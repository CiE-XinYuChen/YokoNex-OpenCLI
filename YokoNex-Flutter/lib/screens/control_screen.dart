import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../api/yokonex_client.dart';

const _motors = ['A', 'B', 'C'];

class ControlScreen extends StatefulWidget {
  const ControlScreen({super.key});

  @override
  State<ControlScreen> createState() => _ControlScreenState();
}

class _ControlScreenState extends State<ControlScreen> {
  bool _stopping = false;

  String get _address =>
      context.read<YokoNexClient>().connectedDeviceAddress ?? '';

  Future<void> _onSpeedChanged(String motor, double value) async {
    final client = context.read<YokoNexClient>();
    final addr   = _address;
    if (addr.isEmpty) return;
    client.motorSpeeds[motor] = value.round();
    await client.setSpeed(
      addr,
      client.motorSpeeds['A']!,
      client.motorSpeeds['B']!,
      client.motorSpeeds['C']!,
    );
  }

  Future<void> _onModeChanged(String motor, int mode) async {
    final client = context.read<YokoNexClient>();
    final addr   = _address;
    if (addr.isEmpty) return;
    await client.setMode(addr, motor, mode);
  }

  Future<void> _stopAll() async {
    final client = context.read<YokoNexClient>();
    final addr   = _address;
    if (addr.isEmpty) return;
    setState(() => _stopping = true);
    try {
      await client.stop(addr);
    } finally {
      if (mounted) setState(() => _stopping = false);
    }
  }

  Future<void> _disconnect() async {
    await context.read<YokoNexClient>().disconnectDevice(_address);
    if (mounted) context.go('/scan');
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<YokoNexClient>(
      builder: (ctx, client, _) {
        // If device disconnected remotely, pop back
        if (client.isConnected && client.connectedDeviceAddress == null &&
            ModalRoute.of(context)?.isCurrent == true) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) context.go('/scan');
          });
        }

        return Scaffold(
          appBar: AppBar(
            title: const Text('Motor Control'),
            actions: [
              IconButton(
                icon: const Icon(Icons.bluetooth_disabled),
                tooltip: 'Disconnect device',
                onPressed: _disconnect,
              ),
            ],
          ),
          body: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                // Device address chip
                Chip(
                  avatar: const Icon(Icons.vibration, size: 16),
                  label: Text(
                    client.connectedDeviceAddress ?? '—',
                    style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                  ),
                ),
                const SizedBox(height: 12),

                // Motor cards
                Expanded(
                  child: ListView(
                    children: _motors
                        .map((m) => _MotorCard(
                              motor:     m,
                              speed:     client.motorSpeeds[m] ?? 0,
                              mode:      client.motorModes[m]  ?? 1,
                              onSpeed:   (v) => _onSpeedChanged(m, v),
                              onMode:    (v) => _onModeChanged(m, v),
                            ))
                        .toList(),
                  ),
                ),

                // Stop all
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    style: FilledButton.styleFrom(
                      backgroundColor: Theme.of(context).colorScheme.error,
                    ),
                    onPressed: _stopping ? null : _stopAll,
                    icon: _stopping
                        ? const SizedBox(width: 18, height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Icon(Icons.stop),
                    label: const Text('Stop All'),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

// ── Motor card ────────────────────────────────────────────────────────────────

class _MotorCard extends StatelessWidget {
  final String motor;
  final int    speed;
  final int    mode;
  final void Function(double) onSpeed;
  final void Function(int)    onMode;

  const _MotorCard({
    required this.motor,
    required this.speed,
    required this.mode,
    required this.onSpeed,
    required this.onMode,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: motor name + speed badge
            Row(
              children: [
                CircleAvatar(
                  radius: 16,
                  backgroundColor: scheme.primaryContainer,
                  child: Text(motor, style: TextStyle(color: scheme.onPrimaryContainer, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(width: 12),
                Text('Speed: $speed', style: Theme.of(context).textTheme.titleMedium),
                const Spacer(),
                // Mode selector
                DropdownButton<int>(
                  value:        mode,
                  items:        List.generate(4, (i) => DropdownMenuItem(
                        value: i + 1,
                        child: Text('Mode ${i + 1}'),
                      )),
                  onChanged:    (v) { if (v != null) onMode(v); },
                  isDense:      true,
                  underline:    const SizedBox(),
                ),
              ],
            ),
            // Speed slider 0-20
            Slider(
              value:    speed.toDouble(),
              min:      0,
              max:      20,
              divisions: 20,
              label:    speed.toString(),
              onChanged: onSpeed,
            ),
          ],
        ),
      ),
    );
  }
}
