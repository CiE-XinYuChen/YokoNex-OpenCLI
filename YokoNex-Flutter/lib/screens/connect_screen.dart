import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/yokonex_client.dart';

class ConnectScreen extends StatefulWidget {
  const ConnectScreen({super.key});

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  final _urlCtrl   = TextEditingController(text: 'ws://');
  final _tokenCtrl = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadSaved();
  }

  Future<void> _loadSaved() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _urlCtrl.text   = prefs.getString('server_url')   ?? 'ws://';
      _tokenCtrl.text = prefs.getString('client_token') ?? '';
    });
  }

  Future<void> _connect() async {
    final url   = _urlCtrl.text.trim();
    final token = _tokenCtrl.text.trim();
    if (url.isEmpty || token.isEmpty) {
      setState(() => _error = 'URL and token are required');
      return;
    }

    setState(() { _loading = true; _error = null; });

    try {
      await context.read<YokoNexClient>().connect(url, token);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('server_url',   url);
      await prefs.setString('client_token', token);
      if (mounted) context.go('/agents');
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('YokoNex')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cable, size: 64),
            const SizedBox(height: 24),
            TextField(
              controller:  _urlCtrl,
              decoration:  const InputDecoration(
                labelText:   'Server URL',
                hintText:    'ws://your-server:8080',
                prefixIcon:  Icon(Icons.cloud),
                border:      OutlineInputBorder(),
              ),
              keyboardType: TextInputType.url,
              autocorrect:  false,
            ),
            const SizedBox(height: 16),
            TextField(
              controller:  _tokenCtrl,
              decoration:  const InputDecoration(
                labelText:  'Client Token',
                prefixIcon: Icon(Icons.key),
                border:     OutlineInputBorder(),
              ),
              obscureText: true,
            ),
            const SizedBox(height: 24),
            if (_error != null) ...[
              Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              const SizedBox(height: 12),
            ],
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _loading ? null : _connect,
                icon: _loading
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.link),
                label: Text(_loading ? 'Connecting…' : 'Connect'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
