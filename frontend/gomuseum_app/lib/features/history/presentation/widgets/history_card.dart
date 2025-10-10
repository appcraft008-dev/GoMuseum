import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../domain/entities/history_item.dart';
import '../../../../theme/tokens.dart';
import '../../../../ui/pages/explanation_page.dart';

class HistoryCard extends StatelessWidget {
  final HistoryItem item;
  final VoidCallback onDelete;

  const HistoryCard({
    super.key,
    required this.item,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: GMSpace.s3),
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(GMRadius.md),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(GMRadius.md),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => ExplanationPage(
                artworkId: item.id,
                artworkName: item.artworkName,
                description: item.description,
              ),
            ),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(GMSpace.s4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.artworkName,
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: Color(GMColors.textPrimary),
                          ),
                        ),
                        const SizedBox(height: GMSpace.s1),
                        Text(
                          item.artist,
                          style: const TextStyle(
                            fontSize: 14,
                            color: Color(GMColors.textSecondary),
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.delete_outline),
                    color: Colors.red[400],
                    onPressed: onDelete,
                  ),
                ],
              ),
              const SizedBox(height: GMSpace.s2),
              Row(
                children: [
                  Icon(
                    Icons.calendar_today,
                    size: 16,
                    color: Colors.grey[600],
                  ),
                  const SizedBox(width: GMSpace.s2),
                  Text(
                    item.period,
                    style: TextStyle(
                      fontSize: 13,
                      color: Colors.grey[700],
                    ),
                  ),
                  const Spacer(),
                  Icon(
                    Icons.access_time,
                    size: 16,
                    color: Colors.grey[600],
                  ),
                  const SizedBox(width: GMSpace.s1),
                  Text(
                    DateFormat('yyyy-MM-dd HH:mm').format(item.timestamp),
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey[600],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: GMSpace.s2),
              Row(
                children: [
                  Icon(
                    Icons.analytics_outlined,
                    size: 16,
                    color: Colors.grey[600],
                  ),
                  const SizedBox(width: GMSpace.s1),
                  Text(
                    'Confidence: ${(item.confidence * 100).toStringAsFixed(1)}%',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey[600],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
