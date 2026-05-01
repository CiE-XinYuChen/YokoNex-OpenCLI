import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../api/yokonex_client.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  List<DeviceInfo> _devices = [];
  bool _scanning  = false;
  bool _connecting = false;
  String? _error;

  Future<void> _scan() async {
    setState(() { _scanning = true; _error = null; _devices = []; });
    try {
      final devices = await context.read<YokoNexClient>().scan(duration: 5);
      setState(() => _devices = devices);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _scanning = false);
    }
  }

  Future<void> _connect(DeviceInfo d) async {
    setState(() { _connecting = true; _error = null; });
    try {
      final ok = await context.read<YokoNexClient>().connectDevice(d.address, d.name);
      if (ok && mounted) {
        context.go('/control');
      } else if (mounted) {
        setState(() => _error = 'Connection failed');
      }
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Devices'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/agents'),
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: (_scanning || _connecting) ? null : _scan,
                icon: _scanning
                    ? const SizedBox(width: 18, height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.bluetooth_searching),
                label: Text(_scanning ? 'Scanning (5 s)…' : 'Scan'),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
            const SizedBox(height: 16),
            if (_devices.isEmpty && !_scanning)
              const Expanded(
                child: Center(child: Text('No devices found.\nTap Scan to search.', textAlign: TextAlign.center)),
              )
            else
              Expanded(
                child: ListView.builder(
                  itemCount: _devices.length,
                  itemBuilder: (_, i) {
                    final d = _devices[i];
                    return Card(
                      child: ListTile(
                        leading: const Icon(Icons.vibration),
                        title:    Text(d.name),
                        subtitle: Text(d.address, style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
                        trailing: _connecting
                            ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.link),
                        onTap: _connecting ? null : () => _connect(d),
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}
