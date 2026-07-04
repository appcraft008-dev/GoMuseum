// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Italian (`it`).
class AppLocalizationsIt extends AppLocalizations {
  AppLocalizationsIt([String locale = 'it']) : super(locale);

  @override
  String get home => 'Home';

  @override
  String get explore => 'Esplora';

  @override
  String get capture => 'Cattura';

  @override
  String get footprints => 'Impronte';

  @override
  String get settings => 'Impostazioni';

  @override
  String get navScan => 'Scansiona';

  @override
  String get artworkRecognition => 'Riconoscimento opere d\'arte';

  @override
  String get takePhoto => 'Scatta foto';

  @override
  String get chooseFromGallery => 'Scegli dalla galleria';

  @override
  String get selectImagePrompt =>
      'Seleziona un\'immagine per riconoscere l\'opera';

  @override
  String get error => 'Errore';

  @override
  String get comingSoon => 'Prossimamente';

  @override
  String get comingSoonShort => 'Prossimamente';

  @override
  String get language => 'Lingua';

  @override
  String get selectLanguage => 'Seleziona lingua';

  @override
  String get retry => 'Riprova';

  @override
  String get cancel => 'Annulla';

  @override
  String get delete => 'Elimina';

  @override
  String get confirm => 'Conferma';

  @override
  String get gotIt => 'Capito';

  @override
  String get loadFailed => 'Caricamento non riuscito';

  @override
  String get loadFailedRetry => 'Caricamento non riuscito, riprova';

  @override
  String get toBeRefined => 'In corso';

  @override
  String get viewAll => 'Vedi tutto →';

  @override
  String get all => 'Tutte';

  @override
  String get homePocketGuide => 'Guida da museo tascabile';

  @override
  String get homeSlogan => 'Avvicinati a un\'opera,\nascolta la sua storia.';

  @override
  String get homeCtaRecognize => 'Fotografa per riconoscere e ascoltare';

  @override
  String homeFreeLeft(Object count) {
    return '$count scansioni gratuite rimaste · Passa all\'accesso completo';
  }

  @override
  String get homeNearby => 'Musei nelle vicinanze';

  @override
  String get statusOpen => 'Aperto';

  @override
  String get exploreTitle => 'Esplora';

  @override
  String get searchCityMuseumArtwork => 'Cerca città, musei o opere';

  @override
  String museumCount(Object count) {
    return '$count musei';
  }

  @override
  String get noMuseums => 'Ancora nessun museo';

  @override
  String get noMatchedMuseums => 'Nessun museo corrispondente';

  @override
  String artworkCountLabel(Object count) {
    return '$count opere';
  }

  @override
  String recordedCount(Object count) {
    return '$count opere nella collezione';
  }

  @override
  String get noArtworks => 'Ancora nessuna opera';

  @override
  String loadingShown(Object shown, Object total) {
    return 'Caricamento · $shown/$total mostrate';
  }

  @override
  String allLoaded(Object total) {
    return 'Tutto caricato · $total in totale';
  }

  @override
  String get guideVoiceGuide => 'Audioguida';

  @override
  String get guideGenFailed => 'Generazione della spiegazione non riuscita';

  @override
  String get guideWriting => 'Sto scrivendo la tua spiegazione…';

  @override
  String get guideHighlight => 'In evidenza';

  @override
  String get guideQa => 'Domande e risposte';

  @override
  String get guideThinking => 'Sto pensando…';

  @override
  String get guideQ1 => 'Cosa rende speciale questo dipinto?';

  @override
  String get guideQ2 => 'Cosa stava vivendo l\'artista in quel periodo?';

  @override
  String get guideAskHint => 'Fai una domanda su questo dipinto…';

  @override
  String get guideAskShort => 'Chiedi su questo dipinto';

  @override
  String get guideVoiceComingSoon =>
      'Le domande vocali arrivano presto, per ora scrivi';

  @override
  String get guideGenerating => 'Generazione contenuti · circa 1–3 min';

  @override
  String get guideEmpty => 'Ancora nessuna spiegazione fondata (in corso)';

  @override
  String get guideInfo => 'Informazioni sull\'opera';

  @override
  String get guideStandardTour => 'Visita standard';

  @override
  String get guideListen => 'Ascolta';

  @override
  String get guideDiveIn => 'Vuoi saperne di più? Tocca sotto';

  @override
  String get guideDeepContent => 'In profondità';

  @override
  String get guideAskPlaceholder => 'Chiedi qualsiasi cosa…';

  @override
  String get guideArtist => 'Artista';

  @override
  String get guideArtistTab => 'Artista';

  @override
  String get guideNotableWorks => 'Opere principali';

  @override
  String get guideNoAnswer => '(nessuna risposta)';

  @override
  String get guideAnswerFailed => 'Risposta non riuscita, riprova più tardi.';

  @override
  String get factInventory => 'N. di inventario';

  @override
  String get factLocation => 'Ubicazione';

  @override
  String get factProvenance => 'Provenienza';

  @override
  String get factExhibitions => 'Mostre';

  @override
  String get factBibliography => 'Bibliografia';

  @override
  String get factArtist => 'Artista';

  @override
  String get factNone => 'Nessuna informazione dettagliata';

  @override
  String get footprintTitle => 'Impronte';

  @override
  String get noFootprints => 'Ancora nessuna impronta';

  @override
  String footprintStat(Object count, Object days) {
    return '$count opere · $days giorni';
  }

  @override
  String get footprintLoadFailed => 'Caricamento delle impronte non riuscito';

  @override
  String get footprintEmptyHint =>
      'Le opere riconosciute vengono salvate qui automaticamente';

  @override
  String get footprintGoRecognize => 'Riconosci la tua prima opera';

  @override
  String itemsCount(Object count) {
    return '$count opere';
  }

  @override
  String get today => 'Oggi';

  @override
  String get yesterday => 'Ieri';

  @override
  String dateMonthDay(Object month, Object day) {
    return '$day/$month';
  }

  @override
  String get deleteFootprintQ => 'Eliminare questa impronta?';

  @override
  String get settingsTitle => 'Impostazioni';

  @override
  String get secGeneral => 'Generale';

  @override
  String get guideLanguage => 'Lingua della guida';

  @override
  String get offlinePacks => 'Pacchetti museo offline';

  @override
  String get autoSavePhoto => 'Salva foto automaticamente';

  @override
  String get ttsVoice => 'Voce TTS';

  @override
  String get ttsVoiceValue => 'Pacata · Femminile';

  @override
  String get ttsVoiceSelect => 'Scegli voce';

  @override
  String get secAccount => 'Account';

  @override
  String get secSupport => 'Supporto e note legali';

  @override
  String get encourageUs => 'Sostienici';

  @override
  String get appStoreRating => 'Valutazione su App Store';

  @override
  String get privacyPolicy => 'Informativa sulla privacy';

  @override
  String get freeQuota => 'Quota di scansioni gratuite';

  @override
  String quotaValue(Object remain, Object total) {
    return '$remain / $total rimaste';
  }

  @override
  String get upgrade => 'Migliora';

  @override
  String get loginBind => 'Accedi / Collega account';

  @override
  String get notLoggedIn => 'Non connesso';

  @override
  String get userDefault => 'Utente';

  @override
  String get guestPrefix => 'Ospite_';

  @override
  String get noEmailBound => 'Nessuna email collegata';

  @override
  String get logout => 'Esci';

  @override
  String get deleteAccount => 'Elimina account';

  @override
  String get loadingShort => 'Caricamento…';

  @override
  String get appearance => 'Aspetto';

  @override
  String get themeLight => 'Chiaro';

  @override
  String get themeDark => 'Scuro';

  @override
  String get themeSystem => 'Sistema';

  @override
  String featureComingSoon(String feature) {
    return '$feature arriva presto';
  }

  @override
  String get privacyBody =>
      'Le foto originali non vengono caricate per impostazione predefinita; i dati di riconoscimento sono elaborati solo temporaneamente. Puoi eliminare il tuo account e i tuoi dati in qualsiasi momento. I termini completi saranno forniti al lancio ufficiale.';

  @override
  String get deleteAccountQ => 'Eliminare definitivamente l\'account?';

  @override
  String get deleteAccountBody =>
      'Questa operazione eliminerà il profilo del tuo account e la quota rimanente. L\'azione è irreversibile.';

  @override
  String get permanentDelete => 'Elimina definitivamente';

  @override
  String get deleteFailed => 'Eliminazione non riuscita, riprova più tardi';

  @override
  String get confirmLogout => 'Conferma disconnessione';

  @override
  String get confirmLogoutBody => 'Vuoi davvero uscire?';

  @override
  String get confirmYes => 'Conferma';

  @override
  String get authEmailHint => 'E-mail';

  @override
  String get authEmailRequired => 'Inserisci la tua e-mail';

  @override
  String get authEmailInvalid => 'Inserisci un\'e-mail valida';

  @override
  String get authPasswordHint => 'Password';

  @override
  String get authPasswordRequired => 'Inserisci la tua password';

  @override
  String get authPasswordMin6 =>
      'La password deve contenere almeno 6 caratteri';

  @override
  String get authConfirmPasswordHint => 'Conferma password';

  @override
  String get authPasswordMismatch => 'Le password non corrispondono';

  @override
  String get authUsernameOptionalHint => 'Nome utente (facoltativo)';

  @override
  String get authLoginButton => 'Accedi';

  @override
  String get authRegisterButton => 'Registrati';

  @override
  String get authNoAccount => 'Non hai un account? Registrati';

  @override
  String get authHaveAccount => 'Hai già un account? Accedi';

  @override
  String get authCreateAccount => 'Crea account';

  @override
  String get authOrLoginWith => 'Oppure accedi con';

  @override
  String get authGoogleLogin => 'Accedi con Google';

  @override
  String get authAppleLogin => 'Accedi con Apple';

  @override
  String get authOr => 'Oppure';

  @override
  String get authGuestLogin => 'Continua come ospite';

  @override
  String get authLoginFailed =>
      'Accesso non riuscito, controlla e-mail e password';

  @override
  String get authRegisterFailed =>
      'Registrazione non riuscita, l\'e-mail potrebbe essere già in uso';

  @override
  String get authGoogleCancelled => 'Accesso con Google annullato';

  @override
  String get authGoogleFailed => 'Accesso con Google non riuscito, riprova';

  @override
  String get authGoogleError => 'Errore di accesso con Google';

  @override
  String get authGoogleNotConfigured =>
      'Accesso con Google non configurato, contatta l\'amministratore';

  @override
  String get authGoogleNetworkError =>
      'Errore di rete nell\'accesso con Google, controlla la connessione';

  @override
  String get authAppleOnlyApple =>
      'L\'accesso con Apple è supportato solo su iOS e macOS';

  @override
  String get authAppleCancelled => 'Accesso con Apple annullato';

  @override
  String get authAppleFailed => 'Accesso con Apple non riuscito, riprova';

  @override
  String get authAppleError => 'Errore di accesso con Apple';

  @override
  String get authAppleNotConfigured => 'Accesso con Apple non configurato';

  @override
  String get authGuestFailed => 'Accesso come ospite non riuscito, riprova';

  @override
  String get authGuestError => 'Errore di accesso come ospite';

  @override
  String get recCandidatesTitle => 'È quest\'opera?';

  @override
  String get recNoneOfThese => 'Nessuna di queste';

  @override
  String get recNotRecognized => 'Opera non riconosciuta';

  @override
  String recLabelSeen(String text) {
    return 'L\'etichetta dice «$text» — non abbiamo ancora la sua guida completa, ma la tua richiesta è stata registrata ✅';
  }

  @override
  String get recShootLabelBtn => 'Fotografa il cartellino';

  @override
  String get recShootLabelHint =>
      'I cartellini del museo mostrano titolo e artista — fotografalo e potremo identificare l\'opera';

  @override
  String get recViewfinderLabelHint =>
      'Inquadra il testo del cartellino, riempi lo schermo';

  @override
  String get camRecognizeTitle => 'Identifica opera';

  @override
  String get camViewfinderHint => 'Inquadra tutta l\'opera';

  @override
  String get camRecentGallery => 'Recenti';

  @override
  String get camAllAlbums => 'Tutti gli album';

  @override
  String get camGallery => 'Galleria';

  @override
  String get camSearch => 'Cerca';

  @override
  String get camNoCamera => 'Nessuna fotocamera disponibile';

  @override
  String get camInitFailed => 'Inizializzazione della fotocamera non riuscita';

  @override
  String get camTagSearch => 'Ricerca per cartellino';

  @override
  String get camTagHint =>
      'Nelle aree senza foto, inserisci numero di cartellino, titolo o artista';

  @override
  String get camTagExample => 'es. INV 3692 / La camera da letto';

  @override
  String get camPackComingSoon =>
      'La ricerca nella collezione si aprirà con i pacchetti offline';

  @override
  String get camQuotaUsedUp => 'Scansioni gratuite esaurite';

  @override
  String get camUpgradeHint =>
      'Migliora per continuare ad ascoltare in tutto il museo';

  @override
  String get camViewUpgrade => 'Vedi i piani';

  @override
  String get camCantPhoto =>
      'Non puoi fotografare? Inserisci il numero di cartellino';

  @override
  String get camRecognizing => 'Riconoscimento…';

  @override
  String get camComparing =>
      'L\'IA confronta con collezioni e banche dati d\'arte pubbliche';

  @override
  String get camConfirmPrompt => 'Riconoscimento completato, conferma l\'opera';

  @override
  String get camConfidence => 'Affidabilità';

  @override
  String get camConfirmStart => 'Conferma e avvia la guida';

  @override
  String get camNoneSearch =>
      'Nessuna corrispondenza? Cerca per titolo o cartellino →';

  @override
  String get camRecognizeFailed => 'Riconoscimento non riuscito';

  @override
  String get camRetake => 'Riscatta';
}
