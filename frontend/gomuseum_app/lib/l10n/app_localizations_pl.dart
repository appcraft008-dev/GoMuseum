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
  String get authOrLoginWith => 'Lub zaloguj się przez';

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
}
