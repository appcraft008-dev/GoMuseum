// lib/ui/explanation_page.dart
import 'package:flutter/material.dart';
import '../theme/tokens.dart';

class ExplanationPage extends StatefulWidget {
  const ExplanationPage({super.key});
  @override
  State<ExplanationPage> createState() => _ExplanationPageState();
}

class _ExplanationPageState extends State<ExplanationPage> {
  bool _isPlaying = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Artwork')),
      body: ListView(
        padding: const EdgeInsets.all(GMSpace.s4),
        children: [
          _Header(),
          const SizedBox(height: GMSpace.s4),
          _PlayBar(
            isPlaying: _isPlaying,
            onToggle: (){
              setState(()=>_isPlaying = !_isPlaying);
              // TODO: TTS play/pause
            },
          ),
          const SizedBox(height: GMSpace.s4),
          const _SectionTitle('Key Points'),
          const _Paragraph('文字讲解与语音同时可用。'),
          const SizedBox(height: GMSpace.s6),
          const _QASection(),
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white, borderRadius: BorderRadius.circular(GMRadius.lg),
        boxShadow: const [BoxShadow(blurRadius: 24, offset: Offset(0,8), color: Color(0x14000000))]
      ),
      child: const Padding(
        padding: EdgeInsets.all(GMSpace.s4),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Artwork Name', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
          SizedBox(height: 4),
          Text('Artist • Museum', style: TextStyle(color: Color(GMColors.textSecondary)))
        ]),
      ),
    );
  }
}

class _PlayBar extends StatelessWidget {
  final bool isPlaying; final VoidCallback onToggle;
  const _PlayBar({required this.isPlaying, required this.onToggle});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(GMSpace.s4),
      decoration: BoxDecoration(
        color: Colors.white, borderRadius: BorderRadius.circular(GMRadius.md),
        boxShadow: const [BoxShadow(blurRadius: 16, offset: Offset(0,6), color: Color(0x12000000))]
      ),
      child: Row(children: [
        IconButton(icon: Icon(isPlaying ? Icons.pause_circle_filled : Icons.play_circle_fill, size: 36), onPressed: onToggle),
        const Expanded(child: LinearProgressIndicator(value: 0.42)),
        const SizedBox(width: GMSpace.s4),
        const Text('01:23')
      ]),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String text; const _SectionTitle(this.text);
  @override
  Widget build(BuildContext context) {
    return Text(text, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600));
  }
}
class _Paragraph extends StatelessWidget {
  final String text; const _Paragraph(this.text);
  @override
  Widget build(BuildContext context) {
    return Text(text, style: const TextStyle(height: 1.6));
  }
}

class _QASection extends StatefulWidget {
  const _QASection();
  @override
  State<_QASection> createState() => _QASectionState();
}
class _QASectionState extends State<_QASection> {
  bool recording = false;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const _SectionTitle('Ask AI'),
      const SizedBox(height: GMSpace.s2),
      Row(children: [
        const Expanded(child: TextField(
          decoration: InputDecoration(
            hintText: 'Type your question...',
            filled: true, fillColor: Colors.white,
            border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(GMRadius.md)), borderSide: BorderSide.none),
          ),
        )),
        const SizedBox(width: GMSpace.s2),
        GestureDetector(
          onLongPressStart: (_){ setState(()=>recording = true); /* TODO: start record */ },
          onLongPressEnd: (_){ setState(()=>recording = false); /* TODO: stop & send */ },
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: recording ? const Color(GMColors.brandAccent) : Colors.white,
              borderRadius: const BorderRadius.all(Radius.circular(GMRadius.pill)),
              boxShadow: const [BoxShadow(blurRadius: 12, color: Color(0x11000000))]
            ),
            child: Icon(recording ? Icons.mic : Icons.mic_none, color: recording ? Colors.white : Colors.black),
          ),
        )
      ])
    ]);
  }
}
