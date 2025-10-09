// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for German (`de`).
class AppLocalizationsDe extends AppLocalizations {
  AppLocalizationsDe([String locale = 'de']) : super(locale);

  @override
  String get appTitle => 'GoMuseum';

  @override
  String get artworkRecognition => 'Kunsterkennung';

  @override
  String get takePhoto => 'Foto aufnehmen';

  @override
  String get chooseFromGallery => 'Aus Galerie wählen';

  @override
  String get selectImagePrompt =>
      'Wählen Sie ein Bild zur Erkennung des Kunstwerks';

  @override
  String get error => 'Fehler';

  @override
  String get settings => 'Einstellungen';

  @override
  String get language => 'Sprache';

  @override
  String get about => 'Über';

  @override
  String get version => 'Version';

  @override
  String get getDetailedExplanation => 'Detaillierte Erklärung erhalten';

  @override
  String get detailLevel => 'Detailgrad';

  @override
  String get brief => 'Kurz';

  @override
  String get standard => 'Standard';

  @override
  String get detailed => 'Detailliert';

  @override
  String get includeAudioNarration => 'Audio-Erzählung einschließen';

  @override
  String get generateAudioVersion => 'Audio-Version der Erklärung generieren';

  @override
  String get regenerateExplanation => 'Erklärung neu generieren';

  @override
  String preparingExplanation(Object artworkName) {
    return 'Vorbereitung der Erklärung für $artworkName...';
  }

  @override
  String get generatingExplanation => 'Erklärung wird generiert...';

  @override
  String get thisIsTakingLonger => 'Dies kann mit Audio einen Moment dauern...';

  @override
  String get failedToGenerate => 'Fehler beim Generieren der Erklärung';

  @override
  String get retry => 'Wiederholen';

  @override
  String get audioNarration => 'Audio-Erzählung';

  @override
  String languageHint(Object languageName) {
    return 'Sprache: $languageName';
  }

  @override
  String get changeInSettings => 'In Einstellungen ändern';

  @override
  String get artist => 'Künstler';

  @override
  String get period => 'Periode';

  @override
  String get confidence => 'Vertrauen';

  @override
  String get recognizedAt => 'Erkannt um';

  @override
  String get description => 'Beschreibung';
}
