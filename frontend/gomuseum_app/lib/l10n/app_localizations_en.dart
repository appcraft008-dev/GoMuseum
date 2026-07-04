// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get home => 'Home';

  @override
  String get explore => 'Explore';

  @override
  String get capture => 'Capture';

  @override
  String get footprints => 'Footprints';

  @override
  String get settings => 'Settings';

  @override
  String get navScan => 'Scan';

  @override
  String get artworkRecognition => 'Artwork Recognition';

  @override
  String get takePhoto => 'Take Photo';

  @override
  String get chooseFromGallery => 'Choose from Gallery';

  @override
  String get selectImagePrompt => 'Select an image to recognize artwork';

  @override
  String get error => 'Error';

  @override
  String get comingSoon => 'Coming Soon';

  @override
  String get comingSoonShort => 'Coming soon';

  @override
  String get language => 'Language';

  @override
  String get selectLanguage => 'Select Language';

  @override
  String get retry => 'Retry';

  @override
  String get cancel => 'Cancel';

  @override
  String get delete => 'Delete';

  @override
  String get confirm => 'Confirm';

  @override
  String get gotIt => 'Got it';

  @override
  String get loadFailed => 'Failed to load';

  @override
  String get loadFailedRetry => 'Failed to load, please retry';

  @override
  String get toBeRefined => 'In progress';

  @override
  String get viewAll => 'View all →';

  @override
  String get all => 'All';

  @override
  String get homePocketGuide => 'Pocket Museum Guide';

  @override
  String get homeSlogan =>
      'Step closer to one work,\nhear the story behind it.';

  @override
  String get homeCtaRecognize => 'Snap to Recognize & Listen';

  @override
  String homeFreeLeft(Object count) {
    return '$count free scans left · Upgrade for full access';
  }

  @override
  String get homeNearby => 'Nearby Museums';

  @override
  String get statusOpen => 'Open';

  @override
  String get exploreTitle => 'Explore';

  @override
  String get searchCityMuseumArtwork => 'Search cities, museums or artworks';

  @override
  String museumCount(Object count) {
    return '$count museums';
  }

  @override
  String get noMuseums => 'No museums yet';

  @override
  String get noMatchedMuseums => 'No matching museums';

  @override
  String artworkCountLabel(Object count) {
    return '$count works';
  }

  @override
  String recordedCount(Object count) {
    return '$count works in collection';
  }

  @override
  String get noArtworks => 'No works yet';

  @override
  String loadingShown(Object shown, Object total) {
    return 'Loading · $shown/$total shown';
  }

  @override
  String allLoaded(Object total) {
    return 'All loaded · $total in total';
  }

  @override
  String get guideVoiceGuide => 'Audio Guide';

  @override
  String get guideGenFailed => 'Failed to generate explanation';

  @override
  String get guideWriting => 'Writing your explanation…';

  @override
  String get guideHighlight => 'Highlight';

  @override
  String get guideQa => 'Q&A';

  @override
  String get guideThinking => 'Thinking…';

  @override
  String get guideQ1 => 'What makes this painting special?';

  @override
  String get guideQ2 => 'What was the artist going through then?';

  @override
  String get guideAskHint => 'Ask about this painting…';

  @override
  String get guideAskShort => 'Ask about this painting';

  @override
  String get guideVoiceComingSoon => 'Voice Q&A is coming soon, type for now';

  @override
  String get guideGenerating => 'Generating content · about 1–3 min';

  @override
  String get guideEmpty => 'No grounded explanation yet (in progress)';

  @override
  String get guideInfo => 'Artwork Info';

  @override
  String get guideStandardTour => 'Standard tour';

  @override
  String get guideListen => 'Listen';

  @override
  String get guideDiveIn => 'Want more? Tap below';

  @override
  String get guideDeepContent => 'In depth';

  @override
  String get guideAskPlaceholder => 'Ask anything…';

  @override
  String get guideArtist => 'Artist';

  @override
  String get guideArtistTab => 'Artist';

  @override
  String get guideNotableWorks => 'Notable works';

  @override
  String get guideNoAnswer => '(no answer returned)';

  @override
  String get guideAnswerFailed => 'Answer failed, please try again later.';

  @override
  String get factInventory => 'Inventory No.';

  @override
  String get factLocation => 'Location';

  @override
  String get factProvenance => 'Provenance';

  @override
  String get factExhibitions => 'Exhibitions';

  @override
  String get factBibliography => 'Bibliography';

  @override
  String get factArtist => 'Artist';

  @override
  String get factNone => 'No detailed information';

  @override
  String get footprintTitle => 'Footprints';

  @override
  String get noFootprints => 'No footprints yet';

  @override
  String footprintStat(Object count, Object days) {
    return '$count works · $days days';
  }

  @override
  String get footprintLoadFailed => 'Failed to load footprints';

  @override
  String get footprintEmptyHint =>
      'Works you recognize are recorded here automatically';

  @override
  String get footprintGoRecognize => 'Recognize your first work';

  @override
  String itemsCount(Object count) {
    return '$count works';
  }

  @override
  String get today => 'Today';

  @override
  String get yesterday => 'Yesterday';

  @override
  String dateMonthDay(Object month, Object day) {
    return '$month/$day';
  }

  @override
  String get deleteFootprintQ => 'Delete this footprint?';

  @override
  String get settingsTitle => 'Settings';

  @override
  String get secGeneral => 'General';

  @override
  String get guideLanguage => 'Guide language';

  @override
  String get offlinePacks => 'Offline museum packs';

  @override
  String get autoSavePhoto => 'Auto-save photos';

  @override
  String get ttsVoice => 'TTS voice';

  @override
  String get ttsVoiceValue => 'Calm · Female';

  @override
  String get ttsVoiceSelect => 'Choose voice';

  @override
  String get secAccount => 'Account';

  @override
  String get secSupport => 'Support & Legal';

  @override
  String get encourageUs => 'Encourage us';

  @override
  String get appStoreRating => 'App Store rating';

  @override
  String get privacyPolicy => 'Privacy policy';

  @override
  String get freeQuota => 'Free scan quota';

  @override
  String quotaValue(Object remain, Object total) {
    return '$remain / $total left';
  }

  @override
  String get upgrade => 'Upgrade';

  @override
  String get loginBind => 'Sign in / Link account';

  @override
  String get notLoggedIn => 'Not signed in';

  @override
  String get userDefault => 'User';

  @override
  String get guestPrefix => 'Guest_';

  @override
  String get noEmailBound => 'No email linked';

  @override
  String get logout => 'Sign out';

  @override
  String get deleteAccount => 'Delete account';

  @override
  String get loadingShort => 'Loading…';

  @override
  String get appearance => 'Appearance';

  @override
  String get themeLight => 'Light';

  @override
  String get themeDark => 'Dark';

  @override
  String get themeSystem => 'System';

  @override
  String featureComingSoon(String feature) {
    return '$feature is coming soon';
  }

  @override
  String get privacyBody =>
      'Original photos are not uploaded by default; recognition data is processed temporarily only. You can delete your account and data anytime. Full terms will be provided at official release.';

  @override
  String get deleteAccountQ => 'Permanently delete account?';

  @override
  String get deleteAccountBody =>
      'This will delete your account profile and remaining quota. This action cannot be undone.';

  @override
  String get permanentDelete => 'Delete permanently';

  @override
  String get deleteFailed => 'Delete failed, please try again later';

  @override
  String get confirmLogout => 'Confirm sign out';

  @override
  String get confirmLogoutBody => 'Are you sure you want to sign out?';

  @override
  String get confirmYes => 'Confirm';

  @override
  String get authEmailHint => 'Email';

  @override
  String get authEmailRequired => 'Please enter your email';

  @override
  String get authEmailInvalid => 'Please enter a valid email';

  @override
  String get authPasswordHint => 'Password';

  @override
  String get authPasswordRequired => 'Please enter your password';

  @override
  String get authPasswordMin6 => 'Password must be at least 6 characters';

  @override
  String get authConfirmPasswordHint => 'Confirm password';

  @override
  String get authPasswordMismatch => 'Passwords do not match';

  @override
  String get authUsernameOptionalHint => 'Username (optional)';

  @override
  String get authLoginButton => 'Log In';

  @override
  String get authRegisterButton => 'Sign Up';

  @override
  String get authNoAccount => 'No account? Sign up';

  @override
  String get authHaveAccount => 'Have an account? Log in';

  @override
  String get authCreateAccount => 'Create account';

  @override
  String get authOrLoginWith => 'Or log in with';

  @override
  String get authGoogleLogin => 'Sign in with Google';

  @override
  String get authAppleLogin => 'Sign in with Apple';

  @override
  String get authOr => 'Or';

  @override
  String get authGuestLogin => 'Continue as guest';

  @override
  String get authLoginFailed => 'Login failed, check your email and password';

  @override
  String get authRegisterFailed =>
      'Registration failed, email may already be in use';

  @override
  String get authGoogleCancelled => 'Google sign-in cancelled';

  @override
  String get authGoogleFailed => 'Google sign-in failed, please try again';

  @override
  String get authGoogleError => 'Google sign-in error';

  @override
  String get authGoogleNotConfigured =>
      'Google sign-in not configured, contact the administrator';

  @override
  String get authGoogleNetworkError =>
      'Google sign-in network error, check your connection';

  @override
  String get authAppleOnlyApple =>
      'Apple sign-in is only supported on iOS and macOS';

  @override
  String get authAppleCancelled => 'Apple sign-in cancelled';

  @override
  String get authAppleFailed => 'Apple sign-in failed, please try again';

  @override
  String get authAppleError => 'Apple sign-in error';

  @override
  String get authAppleNotConfigured => 'Apple sign-in not configured';

  @override
  String get authGuestFailed => 'Guest sign-in failed, please try again';

  @override
  String get authGuestError => 'Guest sign-in error';

  @override
  String get recCandidatesTitle => 'Is this the one?';

  @override
  String get recNoneOfThese => 'None of these';

  @override
  String get recNotRecognized => 'Couldn\'t recognize this work';

  @override
  String recLabelSeen(String text) {
    return 'The label reads \"$text\" — we haven\'t added its full guide yet, but we\'ve noted your request ✅';
  }

  @override
  String get recShootLabelBtn => 'Photograph the wall label';

  @override
  String get recShootLabelHint =>
      'Museum labels show the title and artist — snap it and we can identify the work';

  @override
  String get recViewfinderLabelHint => 'Aim at the label text, fill the frame';

  @override
  String get camRecognizeTitle => 'Identify Artwork';

  @override
  String get camViewfinderHint => 'Fit the whole artwork in the frame';

  @override
  String get camRecentGallery => 'Recent';

  @override
  String get camAllAlbums => 'All albums';

  @override
  String get camGallery => 'Gallery';

  @override
  String get camSearch => 'Search';

  @override
  String get camNoCamera => 'No available camera found';

  @override
  String get camInitFailed => 'Camera initialization failed';

  @override
  String get camTagSearch => 'Label lookup';

  @override
  String get camTagHint =>
      'In no-photo areas, enter the label number, title or artist';

  @override
  String get camTagExample => 'e.g. INV 3692 / The Bedroom';

  @override
  String get camPackComingSoon =>
      'Collection lookup opens after offline packs are available';

  @override
  String get camQuotaUsedUp => 'Free scans used up';

  @override
  String get camUpgradeHint => 'Upgrade to keep listening across the museum';

  @override
  String get camViewUpgrade => 'View upgrade plans';

  @override
  String get camCantPhoto => 'Can\'t take a photo? Enter the label number';

  @override
  String get camRecognizing => 'Recognizing…';

  @override
  String get camComparing =>
      'AI is comparing with collections and public art databases';

  @override
  String get camConfirmPrompt => 'Recognition done, please confirm the work';

  @override
  String get camConfidence => 'Confidence';

  @override
  String get camConfirmStart => 'Confirm & start guide';

  @override
  String get camNoneSearch =>
      'None of these? Search by title or label number →';

  @override
  String get camRecognizeFailed => 'Recognition failed';

  @override
  String get camRetake => 'Retake';
}
