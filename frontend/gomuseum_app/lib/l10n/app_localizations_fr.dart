// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class AppLocalizationsFr extends AppLocalizations {
  AppLocalizationsFr([String locale = 'fr']) : super(locale);

  @override
  String get appTitle => 'GoMuseum';

  @override
  String get artworkRecognition => 'Reconnaissance d\'œuvres d\'art';

  @override
  String get takePhoto => 'Prendre une photo';

  @override
  String get chooseFromGallery => 'Choisir dans la galerie';

  @override
  String get selectImagePrompt =>
      'Sélectionnez une image pour reconnaître l\'œuvre d\'art';

  @override
  String get error => 'Erreur';

  @override
  String get settings => 'Paramètres';

  @override
  String get language => 'Langue';

  @override
  String get about => 'À propos';

  @override
  String get version => 'Version';

  @override
  String get getDetailedExplanation => 'Obtenir une explication détaillée';

  @override
  String get detailLevel => 'Niveau de détail';

  @override
  String get brief => 'Bref';

  @override
  String get standard => 'Standard';

  @override
  String get detailed => 'Détaillé';

  @override
  String get includeAudioNarration => 'Inclure la narration audio';

  @override
  String get generateAudioVersion =>
      'Générer une version audio de l\'explication';

  @override
  String get regenerateExplanation => 'Régénérer l\'explication';

  @override
  String preparingExplanation(Object artworkName) {
    return 'Préparation de l\'explication pour $artworkName...';
  }

  @override
  String get generatingExplanation => 'Génération de l\'explication...';

  @override
  String get thisIsTakingLonger =>
      'Cela peut prendre un moment avec l\'audio...';

  @override
  String get failedToGenerate => 'Échec de la génération de l\'explication';

  @override
  String get retry => 'Réessayer';

  @override
  String get audioNarration => 'Narration audio';

  @override
  String languageHint(Object languageName) {
    return 'Langue : $languageName';
  }

  @override
  String get changeInSettings => 'Changer dans les paramètres';

  @override
  String get artist => 'Artiste';

  @override
  String get period => 'Période';

  @override
  String get confidence => 'Confiance';

  @override
  String get recognizedAt => 'Reconnu à';

  @override
  String get description => 'Description';
}
