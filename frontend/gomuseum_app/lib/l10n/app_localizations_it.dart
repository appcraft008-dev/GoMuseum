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
  String get languageFollowSystem => 'Segui il sistema';

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
  String get homePassActive => 'Pass attivo · accesso completo sbloccato';

  @override
  String get homePassPending => 'Pass acquistato · tocca per attivare';

  @override
  String get homeNearby => 'Musei nelle vicinanze';

  @override
  String get statusOpen => 'Aperto';

  @override
  String get exploreTitle => 'Esplora';

  @override
  String get searchCityMuseumArtwork => 'Cerca città, musei o opere';

  @override
  String get searchMuseumsSection => 'Musei';

  @override
  String get searchArtworksSection => 'Opere';

  @override
  String get searchNoResults => 'Nessun risultato';

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
  String museumCatalogNumbers(Object catalog, Object archive) {
    return 'Catalogo online $catalog opere · archivio $archive voci (riconoscibile/ricercabile)';
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
  String get footprintNoMuseum => 'Luogo sconosciuto';

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
  String dateYearMonthDay(Object day, Object month, Object year) {
    return '$day/$month/$year';
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
  String get autoSavePhotoNeedsAccess =>
      'Serve l\'accesso alla libreria foto per salvare le foto';

  @override
  String get ttsVoice => 'Voce TTS';

  @override
  String get ttsVoiceValue => 'Pacata · Femminile';

  @override
  String get ttsVoiceSelect => 'Scegli voce';

  @override
  String get secAccount => 'Account';

  @override
  String get secSupport => 'Supporto e legale';

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
      'Le foto originali non vengono caricate per impostazione predefinita e i dati di riconoscimento sono elaborati solo temporaneamente. Puoi eliminare account e dati in qualsiasi momento da Impostazioni → Elimina account.';

  @override
  String get privacyFullPolicy => 'Informativa sulla privacy completa';

  @override
  String get privacyCopyLink => 'Copia link';

  @override
  String get privacyLinkCopied => 'Link copiato';

  @override
  String get deleteAccountQ => 'Eliminare definitivamente l\'account?';

  @override
  String get deleteAccountBody =>
      'Questa operazione eliminerà il profilo del tuo account e la quota rimanente. L\'azione è irreversibile.';

  @override
  String get deleteAccountBodyPass =>
      'Il pass acquistato viene annullato subito e non è recuperabile, nemmeno registrandosi di nuovo. Andrebbe riacquistato.';

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
  String get authForgotPassword => 'Password dimenticata?';

  @override
  String get authResetTitle => 'Reimposta la password';

  @override
  String get authResetPrompt =>
      'Inserisci l\'e-mail usata per registrarti. Ti invieremo un link per impostare una nuova password.';

  @override
  String get authResetSend => 'Invia il link';

  @override
  String get authResetSent =>
      'Se quell\'indirizzo è registrato, il link è in arrivo. Controlla anche la posta indesiderata.';

  @override
  String get authResetFailed =>
      'Non è stato possibile inviare l\'e-mail. Riprova tra poco.';

  @override
  String get authNoAccount => 'Non hai un account? Registrati';

  @override
  String get authHaveAccount => 'Hai già un account? Accedi';

  @override
  String get authCreateAccount => 'Crea account';

  @override
  String get authOrWithEmail => 'Oppure con e-mail';

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
  String get recSearchWithLabel => 'Cerca con questo testo';

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
  String get guideUnavailable =>
      'Materiale insufficiente per una guida su quest\'opera';

  @override
  String get guideNotGenerated => 'Guida non ancora generata';

  @override
  String get audioNotReady => 'Audio disponibile quando la guida è pronta';

  @override
  String get audioFailed => 'Audio non disponibile, riprova';

  @override
  String get deepGenerating => 'Generazione dei contenuti di approfondimento…';

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

  @override
  String get museumCoverTab => 'Copertina';

  @override
  String get museumCollectionTab => 'Collezione';

  @override
  String get museumOpeningHours => 'Orari di apertura';

  @override
  String get museumOfficialSite => 'Sito ufficiale';

  @override
  String get museumIntroComingSoon => 'Presentazione del museo in arrivo';

  @override
  String get paywallTitle => 'Pass Parigi 7 giorni';

  @override
  String get paywallPitch =>
      'Riconoscimento fotografico illimitato e audioguida completa al Louvre, a Orsay, all\'Orangerie e al Petit Palais.';

  @override
  String get paywallFreeAlways =>
      'Sfogliare, cercare e leggere il commento completo sono sempre gratuiti.';

  @override
  String get paywallBuy => 'Ottieni il pass';

  @override
  String get paywallRestore => 'Pagato ma niente pass?';

  @override
  String get restoreInProgress => 'Ripristino…';

  @override
  String get restoreNothingFound => 'Nessun pagamento in sospeso';

  @override
  String get restoreSucceeded => 'Il tuo pass è stato ripristinato';

  @override
  String get audioFreePreview => 'Ascolto gratuito';

  @override
  String get audioLockedHint =>
      'L\'audioguida richiede il pass: hai già usato il tuo ascolto gratuito.';

  @override
  String get quotaExhausted => 'Hai esaurito i riconoscimenti gratuiti.';

  @override
  String get activateLater => 'Più tardi';

  @override
  String get paywallLoginToBuy => 'Accedi per acquistare';

  @override
  String get paywallLoginWhy =>
      'Il pass è legato al tuo account: lo ritrovi anche su un nuovo telefono.';

  @override
  String get passActive => 'Pass attivo';

  @override
  String passExpiresOn(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return 'Scade il $dateString';
  }

  @override
  String get passPendingActivation => 'Acquistato · non attivato';

  @override
  String get passActivateHint => 'Parte alla prima riproduzione';

  @override
  String get viewBenefits => 'Vedi vantaggi';

  @override
  String get unlimited => 'Illimitato';

  @override
  String get paywallPriceNote => 'Acquisto unico · non è un abbonamento';

  @override
  String get paywallClockHead => 'Il conteggio non parte all\'acquisto';

  @override
  String get paywallClockBody =>
      'I tuoi 7 giorni iniziano al primo utilizzo confermato di una funzione premium. Compra prima, avvia al museo.';

  @override
  String get paywallLapseNote =>
      'Un pass non attivato scade 30 giorni dopo l\'acquisto.';

  @override
  String get ticketStub => 'Matrice';

  @override
  String get ticketStubPending => 'scadenza da compilare';

  @override
  String get ticketStubUntorn => 'non staccato';

  @override
  String get ticketValidUntil => 'Valido fino al';

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
    return '$days giorni rimasti';
  }

  @override
  String get activateSheetTitle => 'Avviare ora i 7 giorni?';

  @override
  String activateSheetBody(DateTime date, DateTime time) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);
    final intl.DateFormat timeDateFormat = intl.DateFormat.Hm(localeName);
    final String timeString = timeDateFormat.format(time);

    return 'Alla conferma il conteggio parte e termina il $dateString alle $timeString. L\'operazione è irreversibile.';
  }

  @override
  String get activateTear => 'Stacca e avvia';

  @override
  String get activateWaiting => 'Conferma in corso…';

  @override
  String get activateWaitingNote =>
      'Il biglietto non è ancora staccato: vale solo dopo la conferma';

  @override
  String get activateDoneTitle => 'Il tuo pass è attivo';

  @override
  String get activateDoneBody =>
      'Audioguida nei quattro musei e riconoscimento illimitato sono sbloccati.';

  @override
  String get activateDoneCta => 'Continua';

  @override
  String get activateFailTitle =>
      'Conferma non riuscita: il biglietto non è stato usato';

  @override
  String get activateFailBody =>
      'Nessuna connessione, i 7 giorni non sono partiti. Il pass è intatto, riprova.';

  @override
  String get activateRetry => 'Riprova';

  @override
  String get benefitsMyPass => 'Il mio pass';

  @override
  String get benefitsSecFreeQuota => 'Quota gratuita';

  @override
  String get benefitsSecFeatures => 'Funzioni';

  @override
  String get benefitsSecBuyable => 'Disponibile';

  @override
  String get benefitsSecIncluded => 'Incluso';

  @override
  String get benefitsSecUnlocked => 'Sbloccato';

  @override
  String get benefitsSecPurchases => 'Acquisti';

  @override
  String get benefitsSecCurrentQuota => 'La tua quota adesso';

  @override
  String get benefitsSecBuyAnother => 'Un altro pass';

  @override
  String get benefitsRecognition => 'Riconoscimento foto';

  @override
  String get benefitsFreeAudioNote =>
      'Puoi ascoltare gratis il commento audio principale di un\'opera.';

  @override
  String get benefitsFeatBrowse =>
      'Navigazione, ricerca, commento scritto completo';

  @override
  String get benefitsFeatPresetQa => 'Risposte alle domande suggerite';

  @override
  String get benefitsFeatRecognition => 'Riconoscimento foto illimitato';

  @override
  String get benefitsFeatAllAudio =>
      'Commento audio in tutti e quattro i musei';

  @override
  String get benefitsFeatDeepAudio => 'Audio delle sezioni di approfondimento';

  @override
  String get benefitsNeedsPass => 'Serve il pass';

  @override
  String get benefitsNotStartedHead => 'Il conteggio non è ancora partito';

  @override
  String get benefitsNotStartedBody =>
      'La prima volta che userai il commento audio o il riconoscimento al museo ti chiederemo una conferma. I tuoi 7 giorni partono da quel momento.';

  @override
  String get benefitsMuseums => 'Louvre · Orsay · Orangerie · Petit Palais';

  @override
  String get benefitsStartNow => 'Comincia ora i 7 giorni';

  @override
  String get benefitsStartNowNote =>
      'Se non sei ancora al museo, conviene aspettare';

  @override
  String get benefitsExpiredBody =>
      'I tuoi 7 giorni sono finiti. La quota gratuita è tornata e il commento scritto resta completo.';

  @override
  String benefitsPrevPass(DateTime start, DateTime end) {
    final intl.DateFormat startDateFormat = intl.DateFormat.yMMMd(localeName);
    final String startString = startDateFormat.format(start);
    final intl.DateFormat endDateFormat = intl.DateFormat.yMMMd(localeName);
    final String endString = endDateFormat.format(end);

    return 'Pass precedente esaurito · $startString – $endString';
  }

  @override
  String get benefitsEndedAt => 'Terminato il';

  @override
  String get benefitsLapsedHead => 'Questo pass non è mai stato avviato';

  @override
  String get benefitsLapsedBody =>
      'Non è stato usato entro 30 giorni dall\'acquisto ed è scaduto. La tua quota gratuita è tornata e le guide testuali restano complete.';

  @override
  String get benefitsBoughtOn => 'Acquistato il';

  @override
  String benefitsDateOnly(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return '$dateString';
  }

  @override
  String get edgeUnknownHead => 'Ora non riusciamo a leggere il tuo pass';

  @override
  String get edgeUnknownBody =>
      'Senza connessione non possiamo confermare se hai già un pass, né avviare un acquisto in sicurezza.';

  @override
  String get edgeUnknownNote =>
      'Se ne hai già comprato uno, tornerà da solo appena sei online. Non ti verrà addebitato due volte.';

  @override
  String get edgeSignedOutHead => 'Il pass è legato a un account';

  @override
  String get edgeSignedOutBody =>
      'Accedi prima di acquistare: il pass sopravvive a un nuovo telefono o a una reinstallazione.';

  @override
  String get edgeConflictTitle => 'Questo pass è legato a un altro account';

  @override
  String get edgeConflictBody =>
      'Questo acquisto appartiene a un altro account GoMuseum. Lo stesso pass non può servire due account, quindi qui non può essere ripristinato.';

  @override
  String get edgeConflictBound => 'Legato a';

  @override
  String get edgeConflictOther => 'un altro account';

  @override
  String get edgeConflictHelp =>
      'Accedi con l\'account che hai usato per l\'acquisto. Se non ricordi quale sia, o pensi che sia un errore, scrivici e lo verifichiamo.';

  @override
  String get edgeSwitchAccount => 'Cambia account';

  @override
  String get edgeContactSupport => 'Scrivici';

  @override
  String get drawerLockedHint =>
      'L\'audio delle sezioni di approfondimento richiede il pass. Tutto il testo è gratis.';

  @override
  String get drawerLockedCta => 'Vedi il pass';

  @override
  String get purchaseSuccess => 'Acquisto riuscito. Il tuo pass è pronto.';

  @override
  String get purchaseVerifyPending =>
      'Acquisto non ancora confermato. Riaprendo l\'app riproveremo.';

  @override
  String get purchaseFailed => 'L\'acquisto non è andato a buon fine. Riprova.';

  @override
  String get ticketPaid => 'Pagato';

  @override
  String get ticketVoid => 'SCADUTO';

  @override
  String edgeSupportCopied(String email) {
    return 'Indirizzo di assistenza copiato: $email';
  }

  @override
  String get fbTitleObject => 'Segnala un problema';

  @override
  String get fbTitleApp => 'Feedback';

  @override
  String get fbContentWrong => 'Contenuto errato';

  @override
  String get fbAudioBad => 'Pronuncia strana';

  @override
  String get fbAudioMissing => 'Nessun audio';

  @override
  String get fbAppCrash => 'Crash o rallentamenti';

  @override
  String get fbRecognitionBad => 'Riconoscimento impreciso';

  @override
  String get fbFeatureRequest => 'Suggerimento';

  @override
  String get fbOther => 'Altro';

  @override
  String get fbTextHint => 'Altro da aggiungere? (facoltativo)';

  @override
  String get fbSubmit => 'Invia';

  @override
  String get fbThanks => 'Ricevuto, grazie';

  @override
  String get fbFailed => 'Invio non riuscito. Controlla la connessione.';

  @override
  String get fbRetry => 'Riprova';
}
