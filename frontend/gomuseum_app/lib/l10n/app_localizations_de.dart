// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for German (`de`).
class AppLocalizationsDe extends AppLocalizations {
  AppLocalizationsDe([String locale = 'de']) : super(locale);

  @override
  String get home => 'Start';

  @override
  String get explore => 'Entdecken';

  @override
  String get capture => 'Aufnehmen';

  @override
  String get footprints => 'Spuren';

  @override
  String get settings => 'Einstellungen';

  @override
  String get navScan => 'Scannen';

  @override
  String get artworkRecognition => 'Kunstwerk-Erkennung';

  @override
  String get takePhoto => 'Foto aufnehmen';

  @override
  String get chooseFromGallery => 'Aus Galerie wählen';

  @override
  String get selectImagePrompt => 'Wählen Sie ein Bild zur Kunstwerk-Erkennung';

  @override
  String get error => 'Fehler';

  @override
  String get comingSoon => 'Demnächst verfügbar';

  @override
  String get comingSoonShort => 'Demnächst';

  @override
  String get language => 'Sprache';

  @override
  String get selectLanguage => 'Sprache wählen';

  @override
  String get retry => 'Erneut versuchen';

  @override
  String get cancel => 'Abbrechen';

  @override
  String get delete => 'Löschen';

  @override
  String get confirm => 'Bestätigen';

  @override
  String get gotIt => 'Verstanden';

  @override
  String get loadFailed => 'Laden fehlgeschlagen';

  @override
  String get loadFailedRetry => 'Laden fehlgeschlagen, bitte erneut versuchen';

  @override
  String get toBeRefined => 'In Bearbeitung';

  @override
  String get viewAll => 'Alle ansehen →';

  @override
  String get all => 'Alle';

  @override
  String get homePocketGuide => 'Museumsführer für die Tasche';

  @override
  String get homeSlogan =>
      'Treten Sie näher an ein Werk,\nhören Sie seine Geschichte.';

  @override
  String get homeCtaRecognize => 'Fotografieren, erkennen & hören';

  @override
  String homeFreeLeft(Object count) {
    return '$count Gratis-Scans übrig · Upgrade für vollen Zugang';
  }

  @override
  String get homeNearby => 'Museen in der Nähe';

  @override
  String get statusOpen => 'Geöffnet';

  @override
  String get exploreTitle => 'Entdecken';

  @override
  String get searchCityMuseumArtwork => 'Städte, Museen oder Werke suchen';

  @override
  String museumCount(Object count) {
    return '$count Museen';
  }

  @override
  String get noMuseums => 'Noch keine Museen';

  @override
  String get noMatchedMuseums => 'Keine passenden Museen';

  @override
  String artworkCountLabel(Object count) {
    return '$count Werke';
  }

  @override
  String recordedCount(Object count) {
    return '$count Werke in der Sammlung';
  }

  @override
  String get noArtworks => 'Noch keine Werke';

  @override
  String loadingShown(Object shown, Object total) {
    return 'Laden · $shown/$total angezeigt';
  }

  @override
  String allLoaded(Object total) {
    return 'Alle geladen · $total insgesamt';
  }

  @override
  String get guideVoiceGuide => 'Audioguide';

  @override
  String get guideGenFailed => 'Erstellung der Erklärung fehlgeschlagen';

  @override
  String get guideWriting => 'Ihre Erklärung wird geschrieben…';

  @override
  String get guideHighlight => 'Höhepunkt';

  @override
  String get guideQa => 'Fragen & Antworten';

  @override
  String get guideThinking => 'Denke nach…';

  @override
  String get guideQ1 => 'Was macht dieses Gemälde besonders?';

  @override
  String get guideQ2 => 'Was durchlebte der Künstler damals?';

  @override
  String get guideAskHint => 'Fragen Sie zu diesem Gemälde…';

  @override
  String get guideAskShort => 'Zu diesem Gemälde fragen';

  @override
  String get guideVoiceComingSoon =>
      'Sprach-Fragen kommen bald, tippen Sie vorerst';

  @override
  String get guideGenerating => 'Erklärung wird erstellt…';

  @override
  String get guideEmpty => 'Noch keine fundierte Erklärung (in Bearbeitung)';

  @override
  String get guideInfo => 'Werkinfo';

  @override
  String get guideStandardTour => 'Standardführung';

  @override
  String get guideListen => 'Anhören';

  @override
  String get guideDiveIn => 'Mehr erfahren? Unten tippen';

  @override
  String get guideDeepContent => 'Vertiefung';

  @override
  String get guideAskPlaceholder => 'Fragen Sie etwas…';

  @override
  String get guideArtist => 'Künstler';

  @override
  String get guideArtistTab => 'Künstler';

  @override
  String get guideNotableWorks => 'Bedeutende Werke';

  @override
  String get guideNoAnswer => '(keine Antwort erhalten)';

  @override
  String get guideAnswerFailed =>
      'Antwort fehlgeschlagen, bitte später erneut versuchen.';

  @override
  String get factInventory => 'Inventarnr.';

  @override
  String get factLocation => 'Standort';

  @override
  String get factProvenance => 'Provenienz';

  @override
  String get factExhibitions => 'Ausstellungen';

  @override
  String get factBibliography => 'Bibliografie';

  @override
  String get factArtist => 'Künstler';

  @override
  String get factNone => 'Keine detaillierten Informationen';

  @override
  String get footprintTitle => 'Spuren';

  @override
  String get noFootprints => 'Noch keine Spuren';

  @override
  String footprintStat(Object count, Object days) {
    return '$count Werke · $days Tage';
  }

  @override
  String get footprintLoadFailed => 'Laden der Spuren fehlgeschlagen';

  @override
  String get footprintEmptyHint =>
      'Erkannte Werke werden hier automatisch gespeichert';

  @override
  String get footprintGoRecognize => 'Erkennen Sie Ihr erstes Werk';

  @override
  String itemsCount(Object count) {
    return '$count Werke';
  }

  @override
  String get today => 'Heute';

  @override
  String get yesterday => 'Gestern';

  @override
  String dateMonthDay(Object month, Object day) {
    return '$day.$month';
  }

  @override
  String get deleteFootprintQ => 'Diese Spur löschen?';

  @override
  String get settingsTitle => 'Einstellungen';

  @override
  String get secGeneral => 'Allgemein';

  @override
  String get guideLanguage => 'Führungssprache';

  @override
  String get offlinePacks => 'Offline-Museumspakete';

  @override
  String get autoSavePhoto => 'Fotos automatisch speichern';

  @override
  String get ttsVoice => 'TTS-Stimme';

  @override
  String get ttsVoiceValue => 'Ruhig · Weiblich';

  @override
  String get ttsVoiceSelect => 'Stimme wählen';

  @override
  String get secAccount => 'Konto';

  @override
  String get secSupport => 'Support & Rechtliches';

  @override
  String get encourageUs => 'Unterstützen Sie uns';

  @override
  String get appStoreRating => 'App-Store-Bewertung';

  @override
  String get privacyPolicy => 'Datenschutzerklärung';

  @override
  String get freeQuota => 'Gratis-Scan-Kontingent';

  @override
  String quotaValue(Object remain, Object total) {
    return '$remain / $total übrig';
  }

  @override
  String get upgrade => 'Upgrade';

  @override
  String get loginBind => 'Anmelden / Konto verknüpfen';

  @override
  String get notLoggedIn => 'Nicht angemeldet';

  @override
  String get userDefault => 'Benutzer';

  @override
  String get guestPrefix => 'Gast_';

  @override
  String get noEmailBound => 'Keine E-Mail verknüpft';

  @override
  String get logout => 'Abmelden';

  @override
  String get deleteAccount => 'Konto löschen';

  @override
  String get loadingShort => 'Laden…';

  @override
  String get appearance => 'Erscheinungsbild';

  @override
  String get themeLight => 'Hell';

  @override
  String get themeDark => 'Dunkel';

  @override
  String get themeSystem => 'System';

  @override
  String featureComingSoon(String feature) {
    return '$feature kommt bald';
  }

  @override
  String get privacyBody =>
      'Originalfotos werden standardmäßig nicht hochgeladen; Erkennungsdaten werden nur vorübergehend verarbeitet. Sie können Ihr Konto und Ihre Daten jederzeit löschen. Vollständige Bedingungen folgen zur offiziellen Veröffentlichung.';

  @override
  String get deleteAccountQ => 'Konto dauerhaft löschen?';

  @override
  String get deleteAccountBody =>
      'Dies löscht Ihr Kontoprofil und das verbleibende Kontingent. Diese Aktion kann nicht rückgängig gemacht werden.';

  @override
  String get permanentDelete => 'Dauerhaft löschen';

  @override
  String get deleteFailed =>
      'Löschen fehlgeschlagen, bitte später erneut versuchen';

  @override
  String get confirmLogout => 'Abmeldung bestätigen';

  @override
  String get confirmLogoutBody => 'Möchten Sie sich wirklich abmelden?';

  @override
  String get confirmYes => 'Bestätigen';

  @override
  String get camNoCamera => 'Keine Kamera verfügbar';

  @override
  String get camInitFailed => 'Kamera-Initialisierung fehlgeschlagen';

  @override
  String get camTagSearch => 'Schildsuche';

  @override
  String get camTagHint =>
      'In Bereichen ohne Foto: Schildnummer, Titel oder Künstler eingeben';

  @override
  String get camTagExample => 'z. B. INV 3692 / Das Schlafzimmer';

  @override
  String get camPackComingSoon =>
      'Sammlungssuche verfügbar, sobald Offline-Pakete bereitstehen';

  @override
  String get camQuotaUsedUp => 'Gratis-Scans aufgebraucht';

  @override
  String get camUpgradeHint => 'Upgraden, um im ganzen Museum weiterzuhören';

  @override
  String get camViewUpgrade => 'Upgrade-Optionen ansehen';

  @override
  String get camCantPhoto => 'Kein Foto möglich? Schildnummer eingeben';

  @override
  String get camRecognizing => 'Erkenne…';

  @override
  String get camComparing =>
      'KI vergleicht mit Sammlungen und öffentlichen Kunstdatenbanken';

  @override
  String get camConfirmPrompt =>
      'Erkennung abgeschlossen, bitte Werk bestätigen';

  @override
  String get camConfidence => 'Sicherheit';

  @override
  String get camConfirmStart => 'Bestätigen & Führung starten';

  @override
  String get camNoneSearch =>
      'Nichts dabei? Nach Titel oder Schildnummer suchen →';

  @override
  String get camRecognizeFailed => 'Erkennung fehlgeschlagen';

  @override
  String get camRetake => 'Wiederholen';
}
