import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';

void main() {
  group('RecognizedItem.fromJson museum field', () {
    test('parses museum slug when present', () {
      final item = RecognizedItem.fromJson({
        'qid': 'Q1',
        'title': 'Water Lilies',
        'artist': 'Monet',
        'museum': 'orsay',
        'confidence': 0.9,
      });
      expect(item.museum, 'orsay');
    });

    test('missing museum (old backend) → null, no crash', () {
      final item = RecognizedItem.fromJson({
        'qid': 'Q1',
        'title': 'Water Lilies',
        'artist': 'Monet',
        'score': 0.7,
      });
      expect(item.museum, isNull);
    });

    test('museum participates in equality', () {
      RecognizedItem make(String? museum) => RecognizedItem.fromJson({
            'qid': 'Q1',
            'title': 't',
            'artist': 'a',
            'museum': museum,
            'score': 0.5,
          });
      expect(make('orsay'), isNot(equals(make('louvre'))));
      expect(make('orsay'), equals(make('orsay')));
    });
  });

  group('RecognizeResponse.fromJson phash field', () {
    test('parses phash when present', () {
      final r = RecognizeResponse.fromJson(const {
        'outcome': 'candidates',
        'candidates': [
          {'qid': 'Q1', 'title': 't', 'artist': 'a', 'score': 0.5},
        ],
        'phash': 'abc123',
      });
      expect(r.phash, 'abc123');
    });

    test('missing phash (old backend) → null, no crash', () {
      final r = RecognizeResponse.fromJson(const {'outcome': 'unrecognized'});
      expect(r.phash, isNull);
    });
  });
}
