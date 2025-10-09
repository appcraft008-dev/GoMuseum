// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Italian (`it`).
class AppLocalizationsIt extends AppLocalizations {
  AppLocalizationsIt([String locale = 'it']) : super(locale);

  @override
  String get appTitle => 'GoMuseum';

  @override
  String get artworkRecognition => 'Riconoscimento opere d\'arte';

  @override
  String get takePhoto => 'Scatta foto';

  @override
  String get chooseFromGallery => 'Scegli dalla galleria';

  @override
  String get selectImagePrompt =>
      'Seleziona un\'immagine per riconoscere l\'opera d\'arte';

  @override
  String get error => 'Errore';

  @override
  String get settings => 'Impostazioni';

  @override
  String get language => 'Lingua';

  @override
  String get about => 'Informazioni';

  @override
  String get version => 'Versione';

  @override
  String get getDetailedExplanation => 'Ottieni spiegazione dettagliata';

  @override
  String get detailLevel => 'Livello di dettaglio';

  @override
  String get brief => 'Breve';

  @override
  String get standard => 'Standard';

  @override
  String get detailed => 'Dettagliato';

  @override
  String get includeAudioNarration => 'Includi narrazione audio';

  @override
  String get generateAudioVersion => 'Genera versione audio della spiegazione';

  @override
  String get regenerateExplanation => 'Rigenera spiegazione';

  @override
  String preparingExplanation(Object artworkName) {
    return 'Preparazione della spiegazione per $artworkName...';
  }

  @override
  String get generatingExplanation => 'Generazione della spiegazione...';

  @override
  String get thisIsTakingLonger =>
      'Questo può richiedere un momento con l\'audio...';

  @override
  String get failedToGenerate => 'Impossibile generare la spiegazione';

  @override
  String get retry => 'Riprova';

  @override
  String get audioNarration => 'Narrazione audio';

  @override
  String languageHint(Object languageName) {
    return 'Lingua: $languageName';
  }

  @override
  String get changeInSettings => 'Cambia nelle impostazioni';

  @override
  String get artist => 'Artista';

  @override
  String get period => 'Periodo';

  @override
  String get confidence => 'Confidenza';

  @override
  String get recognizedAt => 'Riconosciuto alle';

  @override
  String get description => 'Descrizione';
}
