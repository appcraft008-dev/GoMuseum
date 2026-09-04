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
  String get languageFollowSystem => 'Systemsprache';

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
  String get searchMuseumsSection => 'Museen';

  @override
  String get searchArtworksSection => 'Werke';

  @override
  String get searchNoResults => 'Keine Ergebnisse';

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
  String museumCatalogNumbers(Object catalog, Object archive) {
    return 'Online-Katalog $catalog Werke · Archiv $archive Einträge (erkennbar/durchsuchbar)';
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
  String get guideGenerating => 'Inhalt wird erstellt · etwa 1–3 Min.';

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
      'Originalfotos werden standardmäßig nicht hochgeladen, Erkennungsdaten nur vorübergehend verarbeitet. Konto und Daten können Sie jederzeit unter Einstellungen → Konto löschen löschen.';

  @override
  String get privacyFullPolicy => 'Vollständige Datenschutzerklärung';

  @override
  String get privacyCopyLink => 'Link kopieren';

  @override
  String get privacyLinkCopied => 'Link kopiert';

  @override
  String get deleteAccountQ => 'Konto dauerhaft löschen?';

  @override
  String get deleteAccountBody =>
      'Dies löscht Ihr Kontoprofil und das verbleibende Kontingent. Diese Aktion kann nicht rückgängig gemacht werden.';

  @override
  String get deleteAccountBodyPass =>
      'Ein gekaufter Pass verfällt sofort und lässt sich nicht wiederherstellen — auch nicht mit einem neuen Konto. Er müsste erneut gekauft werden.';

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
  String get authEmailHint => 'E-Mail';

  @override
  String get authEmailRequired => 'Bitte geben Sie Ihre E-Mail ein';

  @override
  String get authEmailInvalid => 'Bitte geben Sie eine gültige E-Mail ein';

  @override
  String get authPasswordHint => 'Passwort';

  @override
  String get authPasswordRequired => 'Bitte geben Sie Ihr Passwort ein';

  @override
  String get authPasswordMin6 =>
      'Das Passwort muss mindestens 6 Zeichen lang sein';

  @override
  String get authConfirmPasswordHint => 'Passwort bestätigen';

  @override
  String get authPasswordMismatch => 'Die Passwörter stimmen nicht überein';

  @override
  String get authUsernameOptionalHint => 'Benutzername (optional)';

  @override
  String get authLoginButton => 'Anmelden';

  @override
  String get authRegisterButton => 'Registrieren';

  @override
  String get authNoAccount => 'Kein Konto? Registrieren';

  @override
  String get authHaveAccount => 'Bereits ein Konto? Anmelden';

  @override
  String get authCreateAccount => 'Konto erstellen';

  @override
  String get authOrWithEmail => 'Oder mit E-Mail';

  @override
  String get authGoogleLogin => 'Mit Google anmelden';

  @override
  String get authAppleLogin => 'Mit Apple anmelden';

  @override
  String get authOr => 'Oder';

  @override
  String get authGuestLogin => 'Als Gast fortfahren';

  @override
  String get authLoginFailed =>
      'Anmeldung fehlgeschlagen, prüfen Sie E-Mail und Passwort';

  @override
  String get authRegisterFailed =>
      'Registrierung fehlgeschlagen, E-Mail wird möglicherweise bereits verwendet';

  @override
  String get authGoogleCancelled => 'Google-Anmeldung abgebrochen';

  @override
  String get authGoogleFailed =>
      'Google-Anmeldung fehlgeschlagen, bitte erneut versuchen';

  @override
  String get authGoogleError => 'Google-Anmeldefehler';

  @override
  String get authGoogleNotConfigured =>
      'Google-Anmeldung nicht konfiguriert, wenden Sie sich an den Administrator';

  @override
  String get authGoogleNetworkError =>
      'Google-Anmeldung Netzwerkfehler, prüfen Sie Ihre Verbindung';

  @override
  String get authAppleOnlyApple =>
      'Apple-Anmeldung wird nur auf iOS und macOS unterstützt';

  @override
  String get authAppleCancelled => 'Apple-Anmeldung abgebrochen';

  @override
  String get authAppleFailed =>
      'Apple-Anmeldung fehlgeschlagen, bitte erneut versuchen';

  @override
  String get authAppleError => 'Apple-Anmeldefehler';

  @override
  String get authAppleNotConfigured => 'Apple-Anmeldung nicht konfiguriert';

  @override
  String get authGuestFailed =>
      'Gast-Anmeldung fehlgeschlagen, bitte erneut versuchen';

  @override
  String get authGuestError => 'Gast-Anmeldefehler';

  @override
  String get recCandidatesTitle => 'Ist es dieses Werk?';

  @override
  String get recNoneOfThese => 'Keines davon';

  @override
  String get recNotRecognized => 'Werk nicht erkannt';

  @override
  String recLabelSeen(String text) {
    return 'Auf dem Schild steht „$text\" — wir haben noch keinen vollständigen Guide dazu, aber Ihre Anfrage ist notiert ✅';
  }

  @override
  String get recShootLabelBtn => 'Wandschild fotografieren';

  @override
  String get recSearchWithLabel => 'Mit diesem Text suchen';

  @override
  String get recShootLabelHint =>
      'Museumsschilder zeigen Titel und Künstler — fotografieren Sie es und wir erkennen das Werk';

  @override
  String get recViewfinderLabelHint =>
      'Auf den Schildtext zielen, Rahmen ausfüllen';

  @override
  String get camRecognizeTitle => 'Werk erkennen';

  @override
  String get camViewfinderHint => 'Das ganze Werk in den Rahmen';

  @override
  String get camRecentGallery => 'Zuletzt';

  @override
  String get camAllAlbums => 'Alle Alben';

  @override
  String get camGallery => 'Galerie';

  @override
  String get camSearch => 'Suche';

  @override
  String get guideUnavailable =>
      'Zu wenig Material für einen Guide zu diesem Werk';

  @override
  String get guideNotGenerated => 'Guide noch nicht erstellt';

  @override
  String get audioNotReady => 'Audio verfügbar, sobald der Guide bereit ist';

  @override
  String get audioFailed => 'Audio nicht verfügbar, bitte erneut versuchen';

  @override
  String get deepGenerating => 'Detailinhalte werden erstellt…';

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

  @override
  String get museumCoverTab => 'Titelseite';

  @override
  String get museumCollectionTab => 'Sammlung';

  @override
  String get museumOpeningHours => 'Öffnungszeiten';

  @override
  String get museumOfficialSite => 'Offizielle Website';

  @override
  String get museumIntroComingSoon => 'Museumsvorstellung folgt in Kürze';

  @override
  String get paywallTitle => 'Paris-Pass für 7 Tage';

  @override
  String get paywallPitch =>
      'Unbegrenzte Fotoerkennung und vollständige Audiokommentare im Louvre, Musée d\'Orsay, in der Orangerie und im Petit Palais.';

  @override
  String get paywallFreeAlways =>
      'Stöbern, Suche und der vollständige Textkommentar bleiben immer kostenlos.';

  @override
  String get paywallBuy => 'Pass holen';

  @override
  String get paywallRestore => 'Bezahlt, aber kein Pass?';

  @override
  String get restoreInProgress => 'Wird wiederhergestellt…';

  @override
  String get restoreNothingFound => 'Keine offene Zahlung gefunden';

  @override
  String get restoreSucceeded => 'Dein Pass wurde wiederhergestellt';

  @override
  String get audioFreePreview => 'Kostenprobe';

  @override
  String get audioLockedHint =>
      'Für Audiokommentare wird der Pass benötigt — deine kostenlose Probe ist bereits aufgebraucht.';

  @override
  String get quotaExhausted =>
      'Du hast alle kostenlosen Erkennungen aufgebraucht.';

  @override
  String get activateLater => 'Später';

  @override
  String get paywallLoginToBuy => 'Zum Kauf anmelden';

  @override
  String get paywallLoginWhy =>
      'Der Pass hängt an deinem Konto – auf einem neuen Handy bleibt er erhalten.';

  @override
  String get passActive => 'Pass aktiv';

  @override
  String passExpiresOn(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return 'Läuft am $dateString ab';
  }

  @override
  String get passPendingActivation => 'Gekauft · nicht aktiviert';

  @override
  String get passActivateHint => 'Startet beim ersten Abspielen';

  @override
  String get viewBenefits => 'Vorteile ansehen';

  @override
  String get unlimited => 'Unbegrenzt';

  @override
  String get paywallPriceNote => 'Einmalkauf · kein Abo';

  @override
  String get paywallClockHead => 'Die Laufzeit beginnt nicht mit dem Kauf';

  @override
  String get paywallClockBody =>
      'Deine 7 Tage starten, wenn du eine Premium-Funktion zum ersten Mal nutzt und bestätigst. Vorab kaufen, im Museum starten.';

  @override
  String get paywallLapseNote =>
      'Ein nicht aktivierter Pass verfällt 30 Tage nach dem Kauf.';

  @override
  String get ticketStub => 'Abschnitt';

  @override
  String get ticketStubPending => 'Enddatum offen';

  @override
  String get ticketStubUntorn => 'nicht abgerissen';

  @override
  String get ticketValidUntil => 'Gültig bis';

  @override
  String ticketDateTime(DateTime date, DateTime time) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);
    final intl.DateFormat timeDateFormat = intl.DateFormat.Hm(localeName);
    final String timeString = timeDateFormat.format(time);

    return '$dateString $timeString';
  }

  @override
  String ticketDaysLeft(int days) {
    return 'noch $days Tage';
  }

  @override
  String get activateSheetTitle => 'Die 7 Tage jetzt starten?';

  @override
  String activateSheetBody(DateTime date, DateTime time) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);
    final intl.DateFormat timeDateFormat = intl.DateFormat.Hm(localeName);
    final String timeString = timeDateFormat.format(time);

    return 'Mit dem Bestätigen läuft die Zeit und endet am $dateString um $timeString. Das lässt sich nicht rückgängig machen.';
  }

  @override
  String get activateTear => 'Abreißen und starten';

  @override
  String get activateWaiting => 'Wird bestätigt…';

  @override
  String get activateWaitingNote =>
      'Das Ticket ist noch nicht abgerissen — es gilt erst nach der Bestätigung';

  @override
  String get activateDoneTitle => 'Dein Pass läuft';

  @override
  String get activateDoneBody =>
      'Audiokommentare in allen vier Museen und unbegrenzte Erkennung sind freigeschaltet.';

  @override
  String get activateDoneCta => 'Weiter';

  @override
  String get activateFailTitle =>
      'Nicht bestätigt — dein Ticket wurde nicht verwendet';

  @override
  String get activateFailBody =>
      'Keine Verbindung, die 7 Tage haben nicht begonnen. Dein Pass ist unversehrt, versuche es erneut.';

  @override
  String get activateRetry => 'Erneut versuchen';

  @override
  String get benefitsMyPass => 'Mein Pass';

  @override
  String get benefitsSecFreeQuota => 'Kostenloses Kontingent';

  @override
  String get benefitsSecFeatures => 'Funktionen';

  @override
  String get benefitsSecBuyable => 'Verfügbar';

  @override
  String get benefitsSecIncluded => 'Enthalten';

  @override
  String get benefitsSecUnlocked => 'Freigeschaltet';

  @override
  String get benefitsSecPurchases => 'Käufe';

  @override
  String get benefitsSecCurrentQuota => 'Ihr aktuelles Kontingent';

  @override
  String get benefitsSecBuyAnother => 'Noch ein Pass';

  @override
  String get benefitsRecognition => 'Fotoerkennung';

  @override
  String get benefitsFreeAudioNote =>
      'Den Haupt-Audiokommentar zu einem Werk können Sie kostenlos anhören.';

  @override
  String get benefitsFeatBrowse =>
      'Stöbern, Suche, vollständiger Textkommentar';

  @override
  String get benefitsFeatPresetQa => 'Antworten auf vorgeschlagene Fragen';

  @override
  String get benefitsFeatRecognition => 'Unbegrenzte Fotoerkennung';

  @override
  String get benefitsFeatAllAudio => 'Audiokommentar in allen vier Museen';

  @override
  String get benefitsFeatDeepAudio => 'Audio für die Vertiefungsabschnitte';

  @override
  String get benefitsNeedsPass => 'Pass nötig';

  @override
  String get benefitsNotStartedHead => 'Die Uhr läuft noch nicht';

  @override
  String get benefitsNotStartedBody =>
      'Wenn Sie im Museum zum ersten Mal den Audiokommentar oder die Erkennung nutzen, bitten wir Sie um eine Bestätigung. Ab diesem Moment laufen Ihre 7 Tage.';

  @override
  String get benefitsMuseums => 'Louvre · Orsay · Orangerie · Petit Palais';

  @override
  String get benefitsStartNow => 'Meine 7 Tage jetzt starten';

  @override
  String get benefitsStartNowNote =>
      'Wenn Sie noch nicht im Museum sind, warten Sie besser';

  @override
  String get benefitsExpiredBody =>
      'Ihre 7 Tage sind vorbei. Das kostenlose Kontingent ist zurück, der Textkommentar bleibt vollständig.';

  @override
  String benefitsPrevPass(DateTime start, DateTime end) {
    final intl.DateFormat startDateFormat = intl.DateFormat.yMMMd(localeName);
    final String startString = startDateFormat.format(start);
    final intl.DateFormat endDateFormat = intl.DateFormat.yMMMd(localeName);
    final String endString = endDateFormat.format(end);

    return 'Vorheriger Pass aufgebraucht · $startString – $endString';
  }

  @override
  String get benefitsEndedAt => 'Beendet am';

  @override
  String get benefitsLapsedHead => 'Dieser Pass wurde nie gestartet';

  @override
  String get benefitsLapsedBody =>
      'Er wurde nicht innerhalb von 30 Tagen nach dem Kauf genutzt und ist abgelaufen. Dein Gratis-Kontingent ist zurück, die Textführungen bleiben vollständig.';

  @override
  String get benefitsBoughtOn => 'Gekauft am';

  @override
  String benefitsDateOnly(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return '$dateString';
  }

  @override
  String get edgeUnknownHead => 'Ihr Pass ist gerade nicht lesbar';

  @override
  String get edgeUnknownBody =>
      'Ohne Verbindung können wir weder bestätigen, dass Sie bereits einen Pass haben, noch einen Kauf sicher starten.';

  @override
  String get edgeUnknownNote =>
      'Falls Sie schon einen gekauft haben, kommt er online automatisch zurück. Doppelt belastet werden Sie nicht.';

  @override
  String get edgeSignedOutHead => 'Der Pass gehört zu einem Konto';

  @override
  String get edgeSignedOutBody =>
      'Melden Sie sich vor dem Kauf an — dann übersteht der Pass ein neues Handy oder eine Neuinstallation.';

  @override
  String get edgeConflictTitle => 'Dieser Pass gehört zu einem anderen Konto';

  @override
  String get edgeConflictBody =>
      'Dieser Kauf gehört zu einem anderen GoMuseum-Konto. Ein Pass kann nicht zwei Konten dienen und lässt sich hier deshalb nicht wiederherstellen.';

  @override
  String get edgeConflictBound => 'Gehört zu';

  @override
  String get edgeConflictOther => 'einem anderen Konto';

  @override
  String get edgeConflictHelp =>
      'Melden Sie sich mit dem Konto an, mit dem Sie gekauft haben. Wenn Sie nicht mehr wissen, welches das war, oder das für einen Fehler halten, schreiben Sie uns — wir schauen nach.';

  @override
  String get edgeSwitchAccount => 'Konto wechseln';

  @override
  String get edgeContactSupport => 'Kontakt aufnehmen';

  @override
  String get drawerLockedHint =>
      'Audio für die Vertiefungsabschnitte braucht den Pass. Alle Texte sind kostenlos.';

  @override
  String get drawerLockedCta => 'Pass ansehen';

  @override
  String get purchaseSuccess => 'Gekauft. Ihr Pass ist bereit.';

  @override
  String get purchaseVerifyPending =>
      'Der Kauf ist noch nicht bestätigt. Beim erneuten Öffnen versuchen wir es wieder.';

  @override
  String get purchaseFailed =>
      'Der Kauf hat nicht geklappt. Bitte erneut versuchen.';

  @override
  String get ticketPaid => 'Bezahlt';

  @override
  String get ticketVoid => 'ABGELAUFEN';

  @override
  String edgeSupportCopied(String email) {
    return 'Support-Adresse kopiert: $email';
  }
}
