import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/explanation/domain/entities/explanation.dart';
import 'package:gomuseum_app/features/explanation/presentation/providers/explanation_provider.dart';
import 'package:gomuseum_app/features/explanation/presentation/widgets/explanation_content_widget.dart';
import 'package:gomuseum_app/features/explanation/presentation/widgets/audio_player_widget.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

/// Explanation page for displaying artwork explanations.
///
/// This page provides a comprehensive interface for viewing AI-generated
/// explanations of artworks with the following features:
/// - Multi-language support
/// - Adjustable detail levels (brief, standard, detailed)
/// - Optional audio narration
/// - Interactive controls for customization
/// - Automatic initial generation on page load
///
/// Example usage:
/// ```dart
/// Navigator.push(
///   context,
///   MaterialPageRoute(
///     builder: (context) => ExplanationPage(
///       artworkName: 'Starry Night',
///       recognitionId: 'rec_123',
///     ),
///   ),
/// );
/// ```
class ExplanationPage extends ConsumerStatefulWidget {
  /// Creates an explanation page.
  ///
  /// Parameters:
  /// - [artworkName]: Name of the artwork to explain (required)
  /// - [recognitionId]: Optional ID of the recognition result
  const ExplanationPage({
    super.key,
    required this.artworkName,
    this.recognitionId,
  });

  /// Name of the artwork to explain.
  final String artworkName;

  /// Optional ID of the recognition result for tracking.
  final String? recognitionId;

  @override
  ConsumerState<ExplanationPage> createState() => _ExplanationPageState();
}

class _ExplanationPageState extends ConsumerState<ExplanationPage> {
  /// Currently selected detail level.
  String _detailLevel = 'standard';

  /// Whether to include audio narration.
  bool _includeAudio = true;

  @override
  void initState() {
    super.initState();
    // Automatically generate explanation on page load
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _generateExplanation();
    });
  }

  /// Generates explanation with current settings.
  void _generateExplanation() {
    // Use global language setting
    final languageCode =
        ref.read(languageNotifierProvider.notifier).currentLanguageCode;

    ref.read(explanationNotifierProvider.notifier).generateExplanation(
          artworkName: widget.artworkName,
          language: languageCode,
          detailLevel: _detailLevel,
          includeAudio: _includeAudio,
          recognitionId: widget.recognitionId,
        );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(explanationNotifierProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.artworkName),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Regenerate explanation',
            onPressed: _generateExplanation,
          ),
        ],
      ),
      body: Column(
        children: [
          _buildControlPanel(),
          const Divider(height: 1),
          Expanded(
            child: _buildBody(state),
          ),
        ],
      ),
    );
  }

  /// Builds the control panel with detail level and audio options.
  Widget _buildControlPanel() {
    final languageState = ref.watch(languageNotifierProvider);

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Language indicator (read-only, change in Settings)
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                Text(
                  languageState.language.flag,
                  style: const TextStyle(fontSize: 24),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Language: ${languageState.language.name}',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      Text(
                        'Change in Settings',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.settings),
                  onPressed: () {
                    Navigator.pushNamed(context, '/settings');
                  },
                  tooltip: 'Open Settings',
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Detail level selector
          Text(
            'Detail Level',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: 8),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(
                value: 'brief',
                label: Text('Brief'),
                icon: Icon(Icons.short_text),
              ),
              ButtonSegment(
                value: 'standard',
                label: Text('Standard'),
                icon: Icon(Icons.text_fields),
              ),
              ButtonSegment(
                value: 'detailed',
                label: Text('Detailed'),
                icon: Icon(Icons.article),
              ),
            ],
            selected: {_detailLevel},
            onSelectionChanged: (Set<String> selection) {
              setState(() => _detailLevel = selection.first);
              _generateExplanation();
            },
          ),
          const SizedBox(height: 16),

          // Audio toggle
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Include Audio Narration'),
            subtitle: const Text('Generate audio version of explanation'),
            value: _includeAudio,
            onChanged: (bool value) {
              setState(() => _includeAudio = value);
              _generateExplanation();
            },
          ),
        ],
      ),
    );
  }

  /// Builds the main body based on current state.
  Widget _buildBody(ExplanationState state) {
    return switch (state) {
      ExplanationInitial() => _buildInitialView(),
      ExplanationLoading() => _buildLoadingView(),
      ExplanationSuccess(:final explanation) =>
        _buildSuccessView(explanation),
      ExplanationError(:final message) => _buildErrorView(message),
      _ => _buildInitialView(), // Fallback for any unexpected state
    };
  }

  /// Builds the initial view shown during first load.
  Widget _buildInitialView() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(
            'Preparing explanation for ${widget.artworkName}...',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ],
      ),
    );
  }

  /// Builds the loading view during explanation generation.
  Widget _buildLoadingView() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(
            'Generating explanation...',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          if (_includeAudio) ...[
            const SizedBox(height: 8),
            Text(
              'This may take a moment with audio...',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ],
      ),
    );
  }

  /// Builds the success view with explanation content and optional audio.
  Widget _buildSuccessView(Explanation explanation) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Main explanation content
          ExplanationContentWidget(explanation: explanation),

          // Audio player (if audio is available)
          if (explanation.audioUrl != null) ...[
            const SizedBox(height: 24),
            Card(
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          Icons.headphones,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'Audio Narration',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    AudioPlayerWidget(
                      audioUrl: explanation.audioUrl!,
                      durationSeconds: explanation.audioDurationSeconds,
                    ),
                  ],
                ),
              ),
            ),
          ],

          // Metadata footer
          const SizedBox(height: 24),
          _buildMetadataFooter(explanation),
        ],
      ),
    );
  }

  /// Builds the error view with retry option.
  Widget _buildErrorView(String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 64,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              'Failed to generate explanation',
              style: Theme.of(context).textTheme.titleLarge,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _generateExplanation,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  /// Builds the metadata footer showing generation details.
  Widget _buildMetadataFooter(Explanation explanation) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(
            Icons.info_outline,
            size: 16,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Generated in ${explanation.language.toUpperCase()} • ${_formatDetailLevel(explanation.metadata.detailLevel)} detail',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ),
        ],
      ),
    );
  }

  /// Formats detail level for display.
  String _formatDetailLevel(String level) {
    return switch (level) {
      'brief' => 'Brief',
      'standard' => 'Standard',
      'detailed' => 'Detailed',
      _ => level,
    };
  }
}
