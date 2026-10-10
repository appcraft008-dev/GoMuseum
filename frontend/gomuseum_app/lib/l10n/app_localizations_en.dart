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
  String get languageFollowSystem => 'Follow system';

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
  String get homePassActive => 'Pass active · full access unlocked';

  @override
  String get homePassPending => 'Pass purchased · tap to activate';

  @override
  String homePassActiveNamed(String name) {
    return '$name active';
  }

  @override
  String homePassPendingNamed(String name) {
    return '$name purchased · tap to activate';
  }

  @override
  String homePassActiveCount(int count) {
    return '$count passes active';
  }

  @override
  String homePassPendingCount(int count) {
    return '$count passes purchased · tap to activate';
  }

  @override
  String get homeNearby => 'Nearby Museums';

  @override
  String get homeMuseums => 'Museums';

  @override
  String get homeEnableLocation => 'Turn on location to see museums near you';

  @override
  String get homeContinue => 'Pick up where you left off';

  @override
  String get statusOpen => 'Open';

  @override
  String get exploreTitle => 'Explore';

  @override
  String get searchCityMuseumArtwork => 'Search cities, museums or artworks';

  @override
  String get searchMuseumsSection => 'Museums';

  @override
  String get searchArtworksSection => 'Artworks';

  @override
  String get searchNoResults => 'No results found';

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
  String museumCatalogNumbers(Object catalog, Object archive) {
    return 'Online catalog $catalog works · archive $archive entries (recognizable/searchable)';
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
  String get footprintNoMuseum => 'Unknown venue';

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
  String ticketDurationDays(String days) {
    return '$days DAYS';
  }

  @override
  String yearBefore(String year) {
    return 'before $year';
  }

  @override
  String yearAfter(String year) {
    return 'after $year';
  }

  @override
  String yearBce(String year) {
    return '$year BC';
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
  String dateYearMonthDay(Object day, Object month, Object year) {
    return '$month/$day/$year';
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
  String get autoSavePhotoNeedsAccess =>
      'Photo library access is needed to save photos';

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
  String get privacyLinkCopied => 'Link copied';

  @override
  String get deleteAccountQ => 'Permanently delete account?';

  @override
  String get deleteAccountBody =>
      'This will delete your account profile and remaining quota. This action cannot be undone.';

  @override
  String get deleteAccountBodyPass =>
      'Any pass you bought is voided immediately and cannot be recovered — not even by signing up again. You would have to buy it anew.';

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
  String get authForgotPassword => 'Forgot your password?';

  @override
  String get authResetTitle => 'Reset password';

  @override
  String get authResetPrompt =>
      'Enter the email you signed up with. We\'ll send a link for setting a new password.';

  @override
  String get authResetSend => 'Send link';

  @override
  String get authResetSent =>
      'If that email is registered, the link is on its way. Check your inbox, and your spam folder.';

  @override
  String get authResetFailed =>
      'Couldn\'t send the email. Please try again in a moment.';

  @override
  String get authNoAccount => 'No account? Sign up';

  @override
  String get authHaveAccount => 'Have an account? Log in';

  @override
  String get authCreateAccount => 'Create account';

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
  String get recThisIsIt => 'This is it';

  @override
  String get recNotRecognized => 'Couldn\'t recognize this work';

  @override
  String recLabelSeen(String text) {
    return 'The label reads \"$text\" — we haven\'t added its full guide yet, but we\'ve noted your request ✅';
  }

  @override
  String get recShootLabelBtn => 'Photograph the wall label';

  @override
  String get recTypeNumberOrName => 'Type the number or title';

  @override
  String get photoFbTitle => 'Send us this photo?';

  @override
  String get photoFbBody =>
      'Used only to add missing works and improve recognition. Kept up to 90 days, never shown to anyone.';

  @override
  String get photoFbConsent => 'Send this photo';

  @override
  String get photoFbNoteHint => 'Add a note (optional)';

  @override
  String get photoFbContinue => 'Continue';

  @override
  String get recSearchWithLabel => 'Search using this text';

  @override
  String get recShootLabelHint =>
      'Museum labels show the title and artist — snap it and we can identify the work';

  @override
  String get recViewfinderLabelHint => 'Aim at the label text, fill the frame';

  @override
  String get camRecognizeTitle => 'Identify Artwork';

  @override
  String get camViewfinderHint =>
      'Fit the whole artwork in the frame\nTurn your phone sideways for wide works';

  @override
  String get camRecentGallery => 'Recent';

  @override
  String get camAllAlbums => 'All albums';

  @override
  String get camGallery => 'Gallery';

  @override
  String get camSearch => 'Search';

  @override
  String get guideUnavailable =>
      'No guide for this artwork in this language yet';

  @override
  String get guideNotGenerated => 'Guide not generated yet';

  @override
  String get guideDailyCap =>
      'Today\'s limit for writing new guides has been reached — please check back tomorrow';

  @override
  String get audioNotReady => 'Audio available once the guide is ready';

  @override
  String get audioFailed => 'Audio unavailable, please retry';

  @override
  String get deepGenerating => 'Generating in-depth content…';

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
  String get recWaitSlow => 'Taking a bit longer than usual — still looking';

  @override
  String get recWaitSwitchApp =>
      'You can switch to another app — the result will be here when you come back';

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

  @override
  String get museumCoverTab => 'Cover';

  @override
  String get museumCollectionTab => 'Collection';

  @override
  String get museumOpeningHours => 'Opening Hours';

  @override
  String get museumOfficialSite => 'Official Website';

  @override
  String get museumIntroComingSoon => 'Museum introduction coming soon';

  @override
  String paywallTitle(String label, String days) {
    return '$label $days-Day Pass';
  }

  @override
  String paywallPitch(String museums) {
    return 'Unlimited photo recognition, plus the audio commentary at $museums.';
  }

  @override
  String get paywallPitchGeneric =>
      'Unlimited photo recognition, plus audio commentary.';

  @override
  String get passNotOnSale => 'Passes for this museum aren\'t on sale yet.';

  @override
  String get paywallFreeAlways =>
      'Browsing, search and full written commentary are always free.';

  @override
  String get paywallBuy => 'Get the pass';

  @override
  String get paywallRestore => 'Paid but no pass?';

  @override
  String get restoreInProgress => 'Restoring…';

  @override
  String get restoreNothingFound => 'No incomplete payment found';

  @override
  String get restoreSucceeded => 'Your pass has been restored';

  @override
  String get audioFreePreview => 'Free preview';

  @override
  String audioLockedHint(String days) {
    return 'Audio commentary needs the pass — artworks you\'ve scanned are free to listen to for $days days.';
  }

  @override
  String audioFreePreviewDays(String days) {
    return 'Free preview · $days days left';
  }

  @override
  String get audioFreeExpiredHint =>
      'The free preview for this artwork has ended — you\'ll need a pass to keep listening.';

  @override
  String get audioPassExpiredHint =>
      'Your pass has expired — get another one to keep listening.';

  @override
  String get quotaExhausted => 'You\'ve used all your free recognitions.';

  @override
  String get activateLater => 'Later';

  @override
  String get paywallLoginToBuy => 'Sign in to buy';

  @override
  String get paywallLoginWhy =>
      'Your pass is tied to your account, so you keep it on a new phone.';

  @override
  String get passActive => 'Pass active';

  @override
  String passExpiresOn(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return 'Expires $dateString';
  }

  @override
  String get passPendingActivation => 'Purchased · not activated';

  @override
  String get passActivateHint => 'Starts when you first play a guide';

  @override
  String get viewBenefits => 'View benefits';

  @override
  String get unlimited => 'Unlimited';

  @override
  String get paywallPriceNote => 'One-time · not a subscription';

  @override
  String get paywallClockHead => 'The clock doesn\'t start at purchase';

  @override
  String paywallClockBody(String days) {
    return 'Your $days days begin the first time you use a premium feature and confirm. Buy ahead, start at the museum.';
  }

  @override
  String get paywallLapseNote =>
      'An unactivated pass lapses 30 days after purchase.';

  @override
  String get ticketStub => 'Stub';

  @override
  String get ticketStubPending => 'expiry to be filled';

  @override
  String get ticketStubUntorn => 'not torn';

  @override
  String get ticketValidUntil => 'Valid until';

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
    String _temp0 = intl.Intl.pluralLogic(
      days,
      locale: localeName,
      other: '$days days left',
      one: '1 day left',
    );
    return '$_temp0';
  }

  @override
  String activateSheetTitle(String days) {
    return 'Start your $days days now?';
  }

  @override
  String activateSheetBody(DateTime date, DateTime time) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);
    final intl.DateFormat timeDateFormat = intl.DateFormat.Hm(localeName);
    final String timeString = timeDateFormat.format(time);

    return 'The clock starts on confirm and ends $dateString $timeString. This can\'t be undone.';
  }

  @override
  String get activateTear => 'Tear it, start now';

  @override
  String get activateWaiting => 'Confirming…';

  @override
  String get activateWaitingNote =>
      'The ticket isn\'t torn yet — it starts once confirmed';

  @override
  String get activateDoneTitle => 'Your pass has started';

  @override
  String get activateDoneBody =>
      'Audio commentary and unlimited recognition are unlocked.';

  @override
  String get activateDoneCta => 'Continue';

  @override
  String get activateFailTitle =>
      'Couldn\'t confirm — your ticket wasn\'t used';

  @override
  String activateFailBody(String days) {
    return 'No connection, so the $days days haven\'t started. Your pass is still intact; try again.';
  }

  @override
  String get activateRetry => 'Try again';

  @override
  String get benefitsMyPass => 'My pass';

  @override
  String get benefitsSecFreeQuota => 'Free allowance';

  @override
  String get benefitsSecFeatures => 'Features';

  @override
  String get benefitsSecBuyable => 'Available';

  @override
  String get benefitsSecIncluded => 'Included';

  @override
  String get benefitsSecUnlocked => 'Unlocked';

  @override
  String get benefitsSecPurchases => 'Purchases';

  @override
  String get benefitsSecCurrentQuota => 'Your allowance now';

  @override
  String get benefitsSecBuyAnother => 'Another pass';

  @override
  String get benefitsRecognition => 'Photo recognition';

  @override
  String get benefitsFreeAudioNote =>
      'For every artwork you scan, the main audio commentary is free. Any other artwork can be unlocked with one free credit.';

  @override
  String get benefitsFeatBrowse => 'Browsing, search, full written commentary';

  @override
  String get benefitsFeatPresetQa => 'Suggested questions answered';

  @override
  String get benefitsFeatRecognition => 'Unlimited photo recognition';

  @override
  String get benefitsFeatAllAudio =>
      'Audio commentary at the museums on your pass';

  @override
  String get benefitsFeatDeepAudio => 'Audio for in-depth sections';

  @override
  String get benefitsNeedsPass => 'Pass needed';

  @override
  String get benefitsNotStartedHead => 'The clock hasn\'t started';

  @override
  String get benefitsPassNotActivated => 'Not activated';

  @override
  String get benefitsPassStartsOnFirstUse => 'Starts on first use at a museum';

  @override
  String benefitsPassVoidAfter(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return 'Void if not activated by $dateString';
  }

  @override
  String get benefitsOtherMuseumsRecognition =>
      'Photo recognition at other museums';

  @override
  String benefitsNotStartedBody(String days) {
    return 'The first time you use audio commentary or recognition at the museum, we\'ll ask you to confirm. Your $days days start from that moment.';
  }

  @override
  String benefitsStartNow(String days) {
    return 'Start my $days days now';
  }

  @override
  String get benefitsStartNowNote =>
      'If you\'re not at the museum yet, it\'s better to wait';

  @override
  String benefitsExpiredBody(String days) {
    return 'Your $days days are up. Your free allowance is back, and written commentary is still complete.';
  }

  @override
  String benefitsPrevPass(DateTime start, DateTime end) {
    final intl.DateFormat startDateFormat = intl.DateFormat.yMMMd(localeName);
    final String startString = startDateFormat.format(start);
    final intl.DateFormat endDateFormat = intl.DateFormat.yMMMd(localeName);
    final String endString = endDateFormat.format(end);

    return 'Previous pass used up · $startString – $endString';
  }

  @override
  String get benefitsEndedAt => 'Ended';

  @override
  String get benefitsLapsedHead => 'This pass was never started';

  @override
  String get benefitsLapsedBody =>
      'It was not used within 30 days of purchase, so it has expired. Your free quota is back, and full text guides remain available.';

  @override
  String get benefitsBoughtOn => 'Purchased';

  @override
  String benefitsDateOnly(DateTime date) {
    final intl.DateFormat dateDateFormat = intl.DateFormat.yMMMd(localeName);
    final String dateString = dateDateFormat.format(date);

    return '$dateString';
  }

  @override
  String get edgeUnknownHead => 'Can\'t read your pass right now';

  @override
  String get edgeUnknownBody =>
      'There\'s no connection, so we can\'t confirm whether you already have a pass — or start a purchase safely.';

  @override
  String get edgeUnknownNote =>
      'If you\'ve already bought one, it comes back automatically once you\'re online. You won\'t be charged twice.';

  @override
  String get edgeSignedOutHead => 'The pass belongs to an account';

  @override
  String get edgeSignedOutBody =>
      'Sign in before buying and it survives a new phone or a reinstall.';

  @override
  String get edgeConflictTitle => 'This pass is tied to another account';

  @override
  String get edgeConflictBody =>
      'This purchase belongs to a different GoMuseum account. One pass can\'t serve two accounts, so it can\'t be restored here.';

  @override
  String get edgeConflictBound => 'Tied to';

  @override
  String get edgeConflictOther => 'another account';

  @override
  String get edgeConflictHelp =>
      'Sign in with the account you bought it on. If you\'re not sure which one, or you think this is a mistake, get in touch and we can look it up.';

  @override
  String get edgeSwitchAccount => 'Switch account';

  @override
  String get edgeContactSupport => 'Contact us';

  @override
  String get drawerLockedHint =>
      'Audio for in-depth sections needs the pass. All the text is free.';

  @override
  String get drawerLockedCta => 'See the pass';

  @override
  String get purchaseSuccess => 'Purchased. Your pass is ready.';

  @override
  String get purchaseVerifyPending =>
      'We couldn\'t confirm the purchase yet. Reopening the app will retry.';

  @override
  String get purchaseFailed =>
      'The purchase didn\'t go through. Please try again.';

  @override
  String get ticketPaid => 'Paid';

  @override
  String get ticketVoid => 'EXPIRED';

  @override
  String edgeSupportCopied(String email) {
    return 'Support address copied: $email';
  }

  @override
  String get fbTitleObject => 'Report an issue';

  @override
  String get fbTitleApp => 'Feedback';

  @override
  String get fbContentWrong => 'Wrong content';

  @override
  String get fbAudioBad => 'Odd pronunciation';

  @override
  String get fbAudioMissing => 'No audio';

  @override
  String get fbAppCrash => 'Crashes or lag';

  @override
  String get fbRecognitionBad => 'Poor recognition';

  @override
  String get fbFeatureRequest => 'Feature request';

  @override
  String get fbOther => 'Something else';

  @override
  String get fbTextHint =>
      'Anything else? (optional — please don\'t include personal information)';

  @override
  String get fbSubmit => 'Submit';

  @override
  String get fbThanks => 'Thanks — we got it';

  @override
  String get fbFailed => 'Couldn\'t send. Check your connection.';

  @override
  String get fbRetry => 'Try again';

  @override
  String get unlockAudioTitle => 'Use one free credit?';

  @override
  String unlockAudioBody(int left) {
    return 'Unlocks the audio commentary for this artwork. $left will be left.';
  }

  @override
  String get unlockAudioCta => 'Unlock and play';

  @override
  String get guideShare => 'Share';

  @override
  String get authUseEmail => 'Use email instead';

  @override
  String authConsent(String terms, String privacy) {
    return 'By continuing you agree to the $terms and $privacy';
  }

  @override
  String get authTermsOfService => 'Terms of Service';

  @override
  String get authConsentPrivacy => 'Privacy Policy';

  @override
  String get updateReady => 'A new version is ready';

  @override
  String get updateRestart => 'Restart';

  @override
  String get collectionViewGrid => 'Show as large images';

  @override
  String get collectionViewList => 'Show as list';
}
