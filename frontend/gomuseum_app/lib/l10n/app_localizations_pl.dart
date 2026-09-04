// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Polish (`pl`).
class AppLocalizationsPl extends AppLocalizations {
  AppLocalizationsPl([String locale = 'pl']) : super(locale);

  @override
  String get home => 'Start';

  @override
  String get explore => 'Odkrywaj';

  @override
  String get capture => 'Aparat';

  @override
  String get footprints => 'Ślady';

  @override
  String get settings => 'Ustawienia';

  @override
  String get navScan => 'Skanuj';

  @override
  String get artworkRecognition => 'Rozpoznawanie dzieł';

  @override
  String get takePhoto => 'Zrób zdjęcie';

  @override
  String get chooseFromGallery => 'Wybierz z galerii';

  @override
  String get selectImagePrompt => 'Wybierz zdjęcie, aby rozpoznać dzieło';

  @override
  String get error => 'Błąd';

  @override
  String get comingSoon => 'Wkrótce';

  @override
  String get comingSoonShort => 'Wkrótce';

  @override
  String get language => 'Język';

  @override
  String get languageFollowSystem => 'Zgodnie z systemem';

  @override
  String get selectLanguage => 'Wybierz język';

  @override
  String get retry => 'Ponów';

  @override
  String get cancel => 'Anuluj';

  @override
  String get delete => 'Usuń';

  @override
  String get confirm => 'Potwierdź';

  @override
  String get gotIt => 'Rozumiem';

  @override
  String get loadFailed => 'Nie udało się załadować';

  @override
  String get loadFailedRetry => 'Nie udało się załadować, spróbuj ponownie';

  @override
  String get toBeRefined => 'W toku';

  @override
  String get viewAll => 'Zobacz wszystko →';

  @override
  String get all => 'Wszystkie';

  @override
  String get homePocketGuide => 'Kieszonkowy przewodnik po muzeum';

  @override
  String get homeSlogan => 'Podejdź bliżej dzieła,\nposłuchaj jego historii.';

  @override
  String get homeCtaRecognize => 'Zrób zdjęcie, aby rozpoznać i słuchać';

  @override
  String homeFreeLeft(Object count) {
    return '$count darmowych skanów · Ulepsz, aby uzyskać pełny dostęp';
  }

  @override
  String get homeNearby => 'Muzea w pobliżu';

  @override
  String get statusOpen => 'Otwarte';

  @override
  String get exploreTitle => 'Odkrywaj';

  @override
  String get searchCityMuseumArtwork => 'Szukaj miast, muzeów lub dzieł';

  @override
  String get searchMuseumsSection => 'Muzea';

  @override
  String get searchArtworksSection => 'Dzieła';

  @override
  String get searchNoResults => 'Brak wyników';

  @override
  String museumCount(Object count) {
    return '$count muzeów';
  }

  @override
  String get noMuseums => 'Brak muzeów';

  @override
  String get noMatchedMuseums => 'Brak pasujących muzeów';

  @override
  String artworkCountLabel(Object count) {
    return '$count dzieł';
  }

  @override
  String recordedCount(Object count) {
    return '$count dzieł w kolekcji';
  }

  @override
  String museumCatalogNumbers(Object catalog, Object archive) {
    return 'Katalog online $catalog dzieł · archiwum $archive wpisów (rozpoznawalne/wyszukiwalne)';
  }

  @override
  String get noArtworks => 'Brak dzieł';

  @override
  String loadingShown(Object shown, Object total) {
    return 'Ładowanie · $shown/$total pokazano';
  }

  @override
  String allLoaded(Object total) {
    return 'Załadowano wszystko · $total łącznie';
  }

  @override
  String get guideVoiceGuide => 'Przewodnik audio';

  @override
  String get guideGenFailed => 'Nie udało się wygenerować opisu';

  @override
  String get guideWriting => 'Piszę Twój opis…';

  @override
  String get guideHighlight => 'Najważniejsze';

  @override
  String get guideQa => 'Pytania i odpowiedzi';

  @override
  String get guideThinking => 'Myślę…';

  @override
  String get guideQ1 => 'Co czyni ten obraz wyjątkowym?';

  @override
  String get guideQ2 => 'Co przeżywał artysta w tamtym czasie?';

  @override
  String get guideAskHint => 'Zapytaj o ten obraz…';

  @override
  String get guideAskShort => 'Zapytaj o ten obraz';

  @override
  String get guideVoiceComingSoon =>
      'Pytania głosowe już wkrótce, na razie pisz';

  @override
  String get guideGenerating => 'Generowanie treści · około 1–3 min';

  @override
  String get guideEmpty => 'Brak ugruntowanego opisu (w toku)';

  @override
  String get guideInfo => 'Informacje o dziele';

  @override
  String get guideStandardTour => 'Zwiedzanie standardowe';

  @override
  String get guideListen => 'Słuchaj';

  @override
  String get guideDiveIn => 'Chcesz więcej? Dotknij poniżej';

  @override
  String get guideDeepContent => 'Szczegółowo';

  @override
  String get guideAskPlaceholder => 'Zapytaj o cokolwiek…';

  @override
  String get guideArtist => 'Artysta';

  @override
  String get guideArtistTab => 'Artysta';

  @override
  String get guideNotableWorks => 'Ważne dzieła';

  @override
  String get guideNoAnswer => '(brak odpowiedzi)';

  @override
  String get guideAnswerFailed =>
      'Odpowiedź nie powiodła się, spróbuj później.';

  @override
  String get factInventory => 'Nr inwentarzowy';

  @override
  String get factLocation => 'Lokalizacja';

  @override
  String get factProvenance => 'Proweniencja';

  @override
  String get factExhibitions => 'Wystawy';

  @override
  String get factBibliography => 'Bibliografia';

  @override
  String get factArtist => 'Artysta';

  @override
  String get factNone => 'Brak szczegółowych informacji';

  @override
  String get footprintTitle => 'Ślady';

  @override
  String get noFootprints => 'Brak śladów';

  @override
  String footprintStat(Object count, Object days) {
    return '$count dzieł · $days dni';
  }

  @override
  String get footprintLoadFailed => 'Nie udało się załadować śladów';

  @override
  String get footprintEmptyHint =>
      'Rozpoznane dzieła są tu zapisywane automatycznie';

  @override
  String get footprintGoRecognize => 'Rozpoznaj swoje pierwsze dzieło';

  @override
  String itemsCount(Object count) {
    return '$count dzieł';
  }

  @override
  String get today => 'Dziś';

  @override
  String get yesterday => 'Wczoraj';

  @override
  String dateMonthDay(Object month, Object day) {
    return '$day.$month';
  }

  @override
  String get deleteFootprintQ => 'Usunąć ten ślad?';

  @override
  String get settingsTitle => 'Ustawienia';

  @override
  String get secGeneral => 'Ogólne';

  @override
  String get guideLanguage => 'Język przewodnika';

  @override
  String get offlinePacks => 'Pakiety muzeów offline';

  @override
  String get autoSavePhoto => 'Automatycznie zapisuj zdjęcia';

  @override
  String get ttsVoice => 'Głos TTS';

  @override
  String get ttsVoiceValue => 'Spokojny · Kobiecy';

  @override
  String get ttsVoiceSelect => 'Wybierz głos';

  @override
  String get secAccount => 'Konto';

  @override
  String get secSupport => 'Pomoc i informacje prawne';

  @override
  String get encourageUs => 'Wesprzyj nas';

  @override
  String get appStoreRating => 'Ocena w App Store';

  @override
  String get privacyPolicy => 'Polityka prywatności';

  @override
  String get freeQuota => 'Limit darmowych skanów';

  @override
  String quotaValue(Object remain, Object total) {
    return '$remain / $total pozostało';
  }

  @override
  String get upgrade => 'Ulepsz';

  @override
  String get loginBind => 'Zaloguj się / Połącz konto';

  @override
  String get notLoggedIn => 'Niezalogowany';

  @override
  String get userDefault => 'Użytkownik';

  @override
  String get guestPrefix => 'Gość_';

  @override
  String get noEmailBound => 'Brak powiązanego e-maila';

  @override
  String get logout => 'Wyloguj się';

  @override
  String get deleteAccount => 'Usuń konto';

  @override
  String get loadingShort => 'Ładowanie…';

  @override
  String get appearance => 'Wygląd';

  @override
  String get themeLight => 'Jasny';

  @override
  String get themeDark => 'Ciemny';

  @override
  String get themeSystem => 'Systemowy';

  @override
  String featureComingSoon(String feature) {
    return '$feature już wkrótce';
  }

  @override
  String get privacyBody =>
      'Oryginalne zdjęcia domyślnie nie są przesyłane; dane rozpoznawania są przetwarzane tylko tymczasowo. Możesz w każdej chwili usunąć konto i dane. Pełny regulamin zostanie udostępniony przy oficjalnej premierze.';

  @override
  String get deleteAccountQ => 'Trwale usunąć konto?';

  @override
  String get deleteAccountBody =>
      'Spowoduje to usunięcie profilu konta i pozostałego limitu. Tej operacji nie można cofnąć.';

  @override
  String get permanentDelete => 'Usuń trwale';

  @override
  String get deleteFailed => 'Usuwanie nie powiodło się, spróbuj później';

  @override
  String get confirmLogout => 'Potwierdź wylogowanie';

  @override
  String get confirmLogoutBody => 'Czy na pewno chcesz się wylogować?';

  @override
  String get confirmYes => 'Potwierdź';

  @override
  String get authEmailHint => 'E-mail';

  @override
  String get authEmailRequired => 'Wprowadź swój e-mail';

  @override
  String get authEmailInvalid => 'Wprowadź prawidłowy e-mail';

  @override
  String get authPasswordHint => 'Hasło';

  @override
  String get authPasswordRequired => 'Wprowadź swoje hasło';

  @override
  String get authPasswordMin6 => 'Hasło musi mieć co najmniej 6 znaków';

  @override
  String get authConfirmPasswordHint => 'Potwierdź hasło';

  @override
  String get authPasswordMismatch => 'Hasła nie są zgodne';

  @override
  String get authUsernameOptionalHint => 'Nazwa użytkownika (opcjonalnie)';

  @override
  String get authLoginButton => 'Zaloguj się';

  @override
  String get authRegisterButton => 'Zarejestruj się';

  @override
  String get authNoAccount => 'Nie masz konta? Zarejestruj się';

  @override
  String get authHaveAccount => 'Masz konto? Zaloguj się';

  @override
  String get authCreateAccount => 'Utwórz konto';

  @override
  String get authOrWithEmail => 'Lub przez e-mail';

  @override
  String get authGoogleLogin => 'Zaloguj się przez Google';

  @override
  String get authAppleLogin => 'Zaloguj się przez Apple';

  @override
  String get authOr => 'Lub';

  @override
  String get authGuestLogin => 'Kontynuuj jako gość';

  @override
  String get authLoginFailed =>
      'Logowanie nie powiodło się, sprawdź e-mail i hasło';

  @override
  String get authRegisterFailed =>
      'Rejestracja nie powiodła się, e-mail może być już używany';

  @override
  String get authGoogleCancelled => 'Anulowano logowanie przez Google';

  @override
  String get authGoogleFailed =>
      'Logowanie przez Google nie powiodło się, spróbuj ponownie';

  @override
  String get authGoogleError => 'Błąd logowania przez Google';

  @override
  String get authGoogleNotConfigured =>
      'Logowanie przez Google nie jest skonfigurowane, skontaktuj się z administratorem';

  @override
  String get authGoogleNetworkError =>
      'Błąd sieci logowania przez Google, sprawdź połączenie';

  @override
  String get authAppleOnlyApple =>
      'Logowanie przez Apple jest obsługiwane tylko na iOS i macOS';

  @override
  String get authAppleCancelled => 'Anulowano logowanie przez Apple';

  @override
  String get authAppleFailed =>
      'Logowanie przez Apple nie powiodło się, spróbuj ponownie';

  @override
  String get authAppleError => 'Błąd logowania przez Apple';

  @override
  String get authAppleNotConfigured =>
      'Logowanie przez Apple nie jest skonfigurowane';

  @override
  String get authGuestFailed =>
      'Logowanie jako gość nie powiodło się, spróbuj ponownie';

  @override
  String get authGuestError => 'Błąd logowania jako gość';

  @override
  String get recCandidatesTitle => 'Czy to jest to dzieło?';

  @override
  String get recNoneOfThese => 'Żadne z nich';

  @override
  String get recNotRecognized => 'Nie rozpoznano tego dzieła';

  @override
  String recLabelSeen(String text) {
    return 'Na etykiecie widnieje „$text” — nie mamy jeszcze pełnego przewodnika, ale odnotowaliśmy Twoją prośbę ✅';
  }

  @override
  String get recShootLabelBtn => 'Sfotografuj tabliczkę';

  @override
  String get recSearchWithLabel => 'Szukaj tym tekstem';

  @override
  String get recShootLabelHint =>
      'Muzealne tabliczki podają tytuł i artystę — sfotografuj ją, a rozpoznamy dzieło';

  @override
  String get recViewfinderLabelHint =>
      'Wyceluj w tekst tabliczki, wypełnij kadr';

  @override
  String get camRecognizeTitle => 'Rozpoznaj dzieło';

  @override
  String get camViewfinderHint => 'Zmieść całe dzieło w kadrze';

  @override
  String get camRecentGallery => 'Ostatnie';

  @override
  String get camAllAlbums => 'Wszystkie albumy';

  @override
  String get camGallery => 'Galeria';

  @override
  String get camSearch => 'Szukaj';

  @override
  String get guideUnavailable =>
      'To dzieło ma zbyt mało materiału na przewodnik';

  @override
  String get guideNotGenerated => 'Przewodnik jeszcze nie wygenerowany';

  @override
  String get audioNotReady => 'Audio dostępne po przygotowaniu przewodnika';

  @override
  String get audioFailed => 'Audio niedostępne, spróbuj ponownie';

  @override
  String get deepGenerating => 'Generowanie szczegółowej treści…';

  @override
  String get camNoCamera => 'Nie znaleziono dostępnego aparatu';

  @override
  String get camInitFailed => 'Nie udało się uruchomić aparatu';

  @override
  String get camTagSearch => 'Wyszukiwanie po tabliczce';

  @override
  String get camTagHint =>
      'W strefach bez zdjęć wpisz numer tabliczki, tytuł lub artystę';

  @override
  String get camTagExample => 'np. INV 3692 / Sypialnia';

  @override
  String get camPackComingSoon =>
      'Przeszukiwanie kolekcji dostępne po pobraniu pakietów offline';

  @override
  String get camQuotaUsedUp => 'Wykorzystano darmowe skany';

  @override
  String get camUpgradeHint => 'Ulepsz, aby słuchać w całym muzeum';

  @override
  String get camViewUpgrade => 'Zobacz plany';

  @override
  String get camCantPhoto => 'Nie możesz zrobić zdjęcia? Wpisz numer tabliczki';

  @override
  String get camRecognizing => 'Rozpoznawanie…';

  @override
  String get camComparing =>
      'AI porównuje z kolekcjami i publicznymi bazami dzieł sztuki';

  @override
  String get camConfirmPrompt => 'Rozpoznano, potwierdź dzieło';

  @override
  String get camConfidence => 'Pewność';

  @override
  String get camConfirmStart => 'Potwierdź i rozpocznij przewodnik';

  @override
  String get camNoneSearch =>
      'Żadne z tych? Szukaj po tytule lub numerze tabliczki →';

  @override
  String get camRecognizeFailed => 'Rozpoznawanie nie powiodło się';

  @override
  String get camRetake => 'Zrób ponownie';

  @override
  String get museumCoverTab => 'Okładka';

  @override
  String get museumCollectionTab => 'Kolekcja';

  @override
  String get museumOpeningHours => 'Godziny otwarcia';

  @override
  String get museumOfficialSite => 'Oficjalna strona';

  @override
  String get museumIntroComingSoon => 'Wprowadzenie do muzeum wkrótce';

  @override
  String get paywallTitle => 'Karnet paryski na 7 dni';

  @override
  String get paywallPitch =>
      'Nielimitowane rozpoznawanie ze zdjęć i pełny komentarz audio w Luwrze, Orsay, Orangerie i Petit Palais.';

  @override
  String get paywallFreeAlways =>
      'Przeglądanie, wyszukiwanie i pełny komentarz tekstowy są zawsze bezpłatne.';

  @override
  String get paywallBuy => 'Kup karnet';

  @override
  String get paywallRestore => 'Przywróć zakup';

  @override
  String get restoreInProgress => 'Przywracanie…';

  @override
  String get restoreNothingFound => 'Brak zakupów do przywrócenia';

  @override
  String get restoreSucceeded => 'Twój bilet został przywrócony';

  @override
  String get audioFreePreview => 'Darmowy odsłuch';

  @override
  String get audioLockedHint =>
      'Komentarz audio wymaga karnetu — darmowy odsłuch został już wykorzystany.';

  @override
  String get quotaExhausted => 'Wykorzystano wszystkie darmowe rozpoznania.';

  @override
  String get activateLater => 'Później';

  @override
  String get paywallLoginToBuy => 'Zaloguj się, aby kupić';

  @override
  String get paywallLoginWhy =>
      'Karnet jest powiązany z kontem — zachowasz go na nowym telefonie.';

  @override
  String get passActive => 'Karnet aktywny';

  @override
  String passExpiresOn(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return 'Wygasa $dateString';
  }

  @override
  String get passPendingActivation => 'Kupiony · nieaktywowany';

  @override
  String get passActivateHint => 'Startuje przy pierwszym odtworzeniu';

  @override
  String get viewBenefits => 'Zobacz korzyści';

  @override
  String get unlimited => 'Bez limitu';

  @override
  String get paywallPriceNote => 'Jednorazowo · to nie abonament';

  @override
  String get paywallClockHead => 'Czas nie zaczyna biec w chwili zakupu';

  @override
  String get paywallClockBody =>
      'Twoje 7 dni rusza przy pierwszym potwierdzonym użyciu funkcji premium. Kup wcześniej, uruchom w muzeum.';

  @override
  String get paywallLapseNote =>
      'Nieaktywowany bilet wygasa 30 dni po zakupie.';

  @override
  String get ticketStub => 'Odcinek';

  @override
  String get ticketStubPending => 'data końca do uzupełnienia';

  @override
  String get ticketStubUntorn => 'nieoderwany';

  @override
  String get ticketValidUntil => 'Ważny do';

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
    return 'pozostało $days dni';
  }

  @override
  String get activateSheetTitle => 'Rozpocząć 7 dni teraz?';

  @override
  String activateSheetBody(DateTime date, DateTime time) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);
    final intl.DateFormat timeDateFormat = intl.DateFormat.Hm(localeName);
    final String timeString = timeDateFormat.format(time);

    return 'Po potwierdzeniu czas rusza i kończy się $dateString o $timeString. Tego nie da się cofnąć.';
  }

  @override
  String get activateTear => 'Oderwij i zacznij';

  @override
  String get activateWaiting => 'Potwierdzanie…';

  @override
  String get activateWaitingNote =>
      'Bilet nie jest jeszcze oderwany — zacznie działać po potwierdzeniu';

  @override
  String get activateDoneTitle => 'Twój karnet ruszył';

  @override
  String get activateDoneBody =>
      'Komentarz audio w czterech muzeach i nielimitowane rozpoznawanie są odblokowane.';

  @override
  String get activateDoneCta => 'Dalej';

  @override
  String get activateFailTitle =>
      'Nie udało się potwierdzić — bilet nie został użyty';

  @override
  String get activateFailBody =>
      'Brak połączenia, 7 dni jeszcze nie ruszyło. Karnet jest nienaruszony, spróbuj ponownie.';

  @override
  String get activateRetry => 'Spróbuj ponownie';

  @override
  String get benefitsMyPass => 'Mój bilet';

  @override
  String get benefitsSecFreeQuota => 'Darmowa pula';

  @override
  String get benefitsSecFeatures => 'Funkcje';

  @override
  String get benefitsSecBuyable => 'Do kupienia';

  @override
  String get benefitsSecIncluded => 'W zestawie';

  @override
  String get benefitsSecUnlocked => 'Odblokowane';

  @override
  String get benefitsSecPurchases => 'Zakupy';

  @override
  String get benefitsSecCurrentQuota => 'Twoja pula teraz';

  @override
  String get benefitsSecBuyAnother => 'Kolejny bilet';

  @override
  String get benefitsRecognition => 'Rozpoznawanie ze zdjęcia';

  @override
  String get benefitsFreeAudioNote =>
      'Główny komentarz audio do jednego dzieła możesz odsłuchać za darmo.';

  @override
  String get benefitsFeatBrowse =>
      'Przeglądanie, wyszukiwanie, pełny komentarz tekstowy';

  @override
  String get benefitsFeatPresetQa => 'Odpowiedzi na proponowane pytania';

  @override
  String get benefitsFeatRecognition =>
      'Nieograniczone rozpoznawanie ze zdjęcia';

  @override
  String get benefitsFeatAllAudio =>
      'Komentarz audio we wszystkich czterech muzeach';

  @override
  String get benefitsFeatDeepAudio => 'Audio do sekcji pogłębionych';

  @override
  String get benefitsNeedsPass => 'Wymaga biletu';

  @override
  String get benefitsNotStartedHead => 'Odliczanie jeszcze się nie zaczęło';

  @override
  String get benefitsNotStartedBody =>
      'Gdy pierwszy raz użyjesz w muzeum komentarza audio lub rozpoznawania, poprosimy o potwierdzenie. Twoje 7 dni ruszy w tym momencie.';

  @override
  String get benefitsMuseums => 'Luwr · Orsay · Orangerie · Petit Palais';

  @override
  String get benefitsStartNow => 'Zacznij moje 7 dni teraz';

  @override
  String get benefitsStartNowNote =>
      'Jeśli nie jesteś jeszcze w muzeum, lepiej poczekaj';

  @override
  String get benefitsExpiredBody =>
      'Twoje 7 dni dobiegło końca. Darmowa pula wróciła, a komentarz tekstowy nadal jest pełny.';

  @override
  String benefitsPrevPass(DateTime start, DateTime end) {
    final intl.DateFormat startDateFormat = intl.DateFormat.yMMMd(localeName);
    final String startString = startDateFormat.format(start);
    final intl.DateFormat endDateFormat = intl.DateFormat.yMMMd(localeName);
    final String endString = endDateFormat.format(end);

    return 'Poprzedni bilet wykorzystany · $startString – $endString';
  }

  @override
  String get benefitsEndedAt => 'Zakończony';

  @override
  String get benefitsLapsedHead => 'Ten bilet nigdy nie został rozpoczęty';

  @override
  String get benefitsLapsedBody =>
      'Nie użyto go w ciągu 30 dni od zakupu, więc wygasł. Twój darmowy limit wrócił, a przewodniki tekstowe pozostają kompletne.';

  @override
  String get benefitsBoughtOn => 'Kupiono';

  @override
  String benefitsDateOnly(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return '$dateString';
  }

  @override
  String get edgeUnknownHead => 'Nie możemy teraz odczytać Twojego biletu';

  @override
  String get edgeUnknownBody =>
      'Bez połączenia nie potwierdzimy, czy masz już bilet, ani nie rozpoczniemy bezpiecznie zakupu.';

  @override
  String get edgeUnknownNote =>
      'Jeśli już go kupiłeś, wróci automatycznie po połączeniu. Nie zapłacisz drugi raz.';

  @override
  String get edgeSeeFree => 'Zobacz darmowe treści';

  @override
  String get edgeSignedOutHead => 'Bilet jest powiązany z kontem';

  @override
  String get edgeSignedOutBody =>
      'Zaloguj się przed zakupem, a bilet przetrwa zmianę telefonu i ponowną instalację.';

  @override
  String get edgeConflictTitle => 'Ten bilet należy do innego konta';

  @override
  String get edgeConflictBody =>
      'Ten zakup należy do innego konta GoMuseum. Jeden bilet nie może służyć dwóm kontom, więc nie da się go tu przywrócić.';

  @override
  String get edgeConflictBound => 'Powiązany z';

  @override
  String get edgeConflictOther => 'innym kontem';

  @override
  String get edgeConflictHelp =>
      'Zaloguj się na konto, z którego kupowałeś. Jeśli nie pamiętasz które to było albo uważasz, że to pomyłka, napisz do nas — sprawdzimy.';

  @override
  String get edgeSwitchAccount => 'Zmień konto';

  @override
  String get edgeContactSupport => 'Napisz do nas';

  @override
  String get drawerLockedHint =>
      'Audio sekcji pogłębionych wymaga biletu. Cały tekst jest darmowy.';

  @override
  String get drawerLockedCta => 'Zobacz bilet';

  @override
  String get purchaseSuccess => 'Zakup udany. Twój bilet jest gotowy.';

  @override
  String get purchaseVerifyPending =>
      'Nie potwierdziliśmy jeszcze zakupu. Ponowne otwarcie aplikacji spróbuje jeszcze raz.';

  @override
  String get purchaseFailed => 'Zakup się nie powiódł. Spróbuj ponownie.';

  @override
  String get ticketPaid => 'Opłacone';

  @override
  String get ticketVoid => 'WYGASŁ';

  @override
  String edgeSupportCopied(String email) {
    return 'Skopiowano adres pomocy: $email';
  }
}
