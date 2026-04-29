import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../api/yokonex_client.dart';

class AgentScreen extends StatefulWidget {
  const AgentScreen({super.key});

  @override
  State<AgentScreen> createState() => _AgentScreenState();
}

class _AgentScreenState extends State<AgentScreen> {
  List<AgentInfo> _agents = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() { _loading = true; _error = null; });
    try {
      final agents = await context.read<YokoNexClient>().listAgents();
      setState(() { _agents = agents; });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _subscribe(AgentInfo agent) async {
    try {
      await context.read<YokoNexClient>().subscribeAgent(agent.id);
      if (mounted) context.go('/scan');
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Subscribe failed: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Select Agent'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/connect'),
        ),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _refresh),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!, style: const TextStyle(color: Colors.red)))
              : _agents.isEmpty
                  ? const Center(child: Text('No agents online.\nStart yokonex server --cloud on your PC.', textAlign: TextAlign.center))
                  : ListView.builder(
                      itemCount: _agents.length,
                      itemBuilder: (_, i) {
                        final a = _agents[i];
                        return ListTile(
                          leading: const Icon(Icons.computer),
                          title: Text(a.id),
                          subtitle: Text('${a.clients} client(s) connected'),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => _subscribe(a),
                        );
                      },
                    ),
    );
  }
}
