import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_de.dart';
import 'app_localizations_en.dart';
import 'app_localizations_es.dart';
import 'app_localizations_fr.dart';
import 'app_localizations_it.dart';
import 'app_localizations_ja.dart';
import 'app_localizations_ko.dart';
import 'app_localizations_pl.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('de'),
    Locale('en'),
    Locale('es'),
    Locale('fr'),
    Locale('it'),
    Locale('ja'),
    Locale('ko'),
    Locale('pl'),
    Locale('zh'),
    Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant')
  ];

  /// No description provided for @home.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get home;

  /// No description provided for @explore.
  ///
  /// In en, this message translates to:
  /// **'Explore'**
  String get explore;

  /// No description provided for @capture.
  ///
  /// In en, this message translates to:
  /// **'Capture'**
  String get capture;

  /// No description provided for @footprints.
  ///
  /// In en, this message translates to:
  /// **'Footprints'**
  String get footprints;

  /// No description provided for @settings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settings;

  /// No description provided for @navScan.
  ///
  /// In en, this message translates to:
  /// **'Scan'**
  String get navScan;

  /// No description provided for @artworkRecognition.
  ///
  /// In en, this message translates to:
  /// **'Artwork Recognition'**
  String get artworkRecognition;

  /// No description provided for @takePhoto.
  ///
  /// In en, this message translates to:
  /// **'Take Photo'**
  String get takePhoto;

  /// No description provided for @chooseFromGallery.
  ///
  /// In en, this message translates to:
  /// **'Choose from Gallery'**
  String get chooseFromGallery;

  /// No description provided for @selectImagePrompt.
  ///
  /// In en, this message translates to:
  /// **'Select an image to recognize artwork'**
  String get selectImagePrompt;

  /// No description provided for @error.
  ///
  /// In en, this message translates to:
  /// **'Error'**
  String get error;

  /// No description provided for @comingSoon.
  ///
  /// In en, this message translates to:
  /// **'Coming Soon'**
  String get comingSoon;

  /// No description provided for @comingSoonShort.
  ///
  /// In en, this message translates to:
  /// **'Coming soon'**
  String get comingSoonShort;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// Language option meaning: use the device's system language
  ///
  /// In en, this message translates to:
  /// **'Follow system'**
  String get languageFollowSystem;

  /// No description provided for @selectLanguage.
  ///
  /// In en, this message translates to:
  /// **'Select Language'**
  String get selectLanguage;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @delete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// No description provided for @confirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirm;

  /// No description provided for @gotIt.
  ///
  /// In en, this message translates to:
  /// **'Got it'**
  String get gotIt;

  /// No description provided for @loadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load'**
  String get loadFailed;

  /// No description provided for @loadFailedRetry.
  ///
  /// In en, this message translates to:
  /// **'Failed to load, please retry'**
  String get loadFailedRetry;

  /// No description provided for @toBeRefined.
  ///
  /// In en, this message translates to:
  /// **'In progress'**
  String get toBeRefined;

  /// No description provided for @viewAll.
  ///
  /// In en, this message translates to:
  /// **'View all →'**
  String get viewAll;

  /// No description provided for @all.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get all;

  /// No description provided for @homePocketGuide.
  ///
  /// In en, this message translates to:
  /// **'Pocket Museum Guide'**
  String get homePocketGuide;

  /// No description provided for @homeSlogan.
  ///
  /// In en, this message translates to:
  /// **'Step closer to one work,\nhear the story behind it.'**
  String get homeSlogan;

  /// No description provided for @homeCtaRecognize.
  ///
  /// In en, this message translates to:
  /// **'Snap to Recognize & Listen'**
  String get homeCtaRecognize;

  /// No description provided for @homeFreeLeft.
  ///
  /// In en, this message translates to:
  /// **'{count} free scans left · Upgrade for full access'**
  String homeFreeLeft(Object count);

  /// No description provided for @homePassActive.
  ///
  /// In en, this message translates to:
  /// **'Pass active · full access unlocked'**
  String get homePassActive;

  /// No description provided for @homePassPending.
  ///
  /// In en, this message translates to:
  /// **'Pass purchased · tap to activate'**
  String get homePassPending;

  /// No description provided for @homeNearby.
  ///
  /// In en, this message translates to:
  /// **'Nearby Museums'**
  String get homeNearby;

  /// No description provided for @statusOpen.
  ///
  /// In en, this message translates to:
  /// **'Open'**
  String get statusOpen;

  /// No description provided for @exploreTitle.
  ///
  /// In en, this message translates to:
  /// **'Explore'**
  String get exploreTitle;

  /// No description provided for @searchCityMuseumArtwork.
  ///
  /// In en, this message translates to:
  /// **'Search cities, museums or artworks'**
  String get searchCityMuseumArtwork;

  /// No description provided for @searchMuseumsSection.
  ///
  /// In en, this message translates to:
  /// **'Museums'**
  String get searchMuseumsSection;

  /// No description provided for @searchArtworksSection.
  ///
  /// In en, this message translates to:
  /// **'Artworks'**
  String get searchArtworksSection;

  /// No description provided for @searchNoResults.
  ///
  /// In en, this message translates to:
  /// **'No results found'**
  String get searchNoResults;

  /// No description provided for @museumCount.
  ///
  /// In en, this message translates to:
  /// **'{count} museums'**
  String museumCount(Object count);

  /// No description provided for @noMuseums.
  ///
  /// In en, this message translates to:
  /// **'No museums yet'**
  String get noMuseums;

  /// No description provided for @noMatchedMuseums.
  ///
  /// In en, this message translates to:
  /// **'No matching museums'**
  String get noMatchedMuseums;

  /// No description provided for @artworkCountLabel.
  ///
  /// In en, this message translates to:
  /// **'{count} works'**
  String artworkCountLabel(Object count);

  /// No description provided for @recordedCount.
  ///
  /// In en, this message translates to:
  /// **'{count} works in collection'**
  String recordedCount(Object count);

  /// No description provided for @museumCatalogNumbers.
  ///
  /// In en, this message translates to:
  /// **'Online catalog {catalog} works · archive {archive} entries (recognizable/searchable)'**
  String museumCatalogNumbers(Object catalog, Object archive);

  /// No description provided for @noArtworks.
  ///
  /// In en, this message translates to:
  /// **'No works yet'**
  String get noArtworks;

  /// No description provided for @loadingShown.
  ///
  /// In en, this message translates to:
  /// **'Loading · {shown}/{total} shown'**
  String loadingShown(Object shown, Object total);

  /// No description provided for @allLoaded.
  ///
  /// In en, this message translates to:
  /// **'All loaded · {total} in total'**
  String allLoaded(Object total);

  /// No description provided for @guideVoiceGuide.
  ///
  /// In en, this message translates to:
  /// **'Audio Guide'**
  String get guideVoiceGuide;

  /// No description provided for @guideGenFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to generate explanation'**
  String get guideGenFailed;

  /// No description provided for @guideWriting.
  ///
  /// In en, this message translates to:
  /// **'Writing your explanation…'**
  String get guideWriting;

  /// No description provided for @guideHighlight.
  ///
  /// In en, this message translates to:
  /// **'Highlight'**
  String get guideHighlight;

  /// No description provided for @guideQa.
  ///
  /// In en, this message translates to:
  /// **'Q&A'**
  String get guideQa;

  /// No description provided for @guideThinking.
  ///
  /// In en, this message translates to:
  /// **'Thinking…'**
  String get guideThinking;

  /// No description provided for @guideQ1.
  ///
  /// In en, this message translates to:
  /// **'What makes this painting special?'**
  String get guideQ1;

  /// No description provided for @guideQ2.
  ///
  /// In en, this message translates to:
  /// **'What was the artist going through then?'**
  String get guideQ2;

  /// No description provided for @guideAskHint.
  ///
  /// In en, this message translates to:
  /// **'Ask about this painting…'**
  String get guideAskHint;

  /// No description provided for @guideAskShort.
  ///
  /// In en, this message translates to:
  /// **'Ask about this painting'**
  String get guideAskShort;

  /// No description provided for @guideVoiceComingSoon.
  ///
  /// In en, this message translates to:
  /// **'Voice Q&A is coming soon, type for now'**
  String get guideVoiceComingSoon;

  /// No description provided for @guideGenerating.
  ///
  /// In en, this message translates to:
  /// **'Generating content · about 1–3 min'**
  String get guideGenerating;

  /// No description provided for @guideEmpty.
  ///
  /// In en, this message translates to:
  /// **'No grounded explanation yet (in progress)'**
  String get guideEmpty;

  /// No description provided for @guideInfo.
  ///
  /// In en, this message translates to:
  /// **'Artwork Info'**
  String get guideInfo;

  /// No description provided for @guideStandardTour.
  ///
  /// In en, this message translates to:
  /// **'Standard tour'**
  String get guideStandardTour;

  /// No description provided for @guideListen.
  ///
  /// In en, this message translates to:
  /// **'Listen'**
  String get guideListen;

  /// No description provided for @guideDiveIn.
  ///
  /// In en, this message translates to:
  /// **'Want more? Tap below'**
  String get guideDiveIn;

  /// No description provided for @guideDeepContent.
  ///
  /// In en, this message translates to:
  /// **'In depth'**
  String get guideDeepContent;

  /// No description provided for @guideAskPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Ask anything…'**
  String get guideAskPlaceholder;

  /// No description provided for @guideArtist.
  ///
  /// In en, this message translates to:
  /// **'Artist'**
  String get guideArtist;

  /// No description provided for @guideArtistTab.
  ///
  /// In en, this message translates to:
  /// **'Artist'**
  String get guideArtistTab;

  /// No description provided for @guideNotableWorks.
  ///
  /// In en, this message translates to:
  /// **'Notable works'**
  String get guideNotableWorks;

  /// No description provided for @guideNoAnswer.
  ///
  /// In en, this message translates to:
  /// **'(no answer returned)'**
  String get guideNoAnswer;

  /// No description provided for @guideAnswerFailed.
  ///
  /// In en, this message translates to:
  /// **'Answer failed, please try again later.'**
  String get guideAnswerFailed;

  /// No description provided for @factInventory.
  ///
  /// In en, this message translates to:
  /// **'Inventory No.'**
  String get factInventory;

  /// No description provided for @factLocation.
  ///
  /// In en, this message translates to:
  /// **'Location'**
  String get factLocation;

  /// No description provided for @factProvenance.
  ///
  /// In en, this message translates to:
  /// **'Provenance'**
  String get factProvenance;

  /// No description provided for @factExhibitions.
  ///
  /// In en, this message translates to:
  /// **'Exhibitions'**
  String get factExhibitions;

  /// No description provided for @factBibliography.
  ///
  /// In en, this message translates to:
  /// **'Bibliography'**
  String get factBibliography;

  /// No description provided for @factArtist.
  ///
  /// In en, this message translates to:
  /// **'Artist'**
  String get factArtist;

  /// No description provided for @factNone.
  ///
  /// In en, this message translates to:
  /// **'No detailed information'**
  String get factNone;

  /// No description provided for @footprintTitle.
  ///
  /// In en, this message translates to:
  /// **'Footprints'**
  String get footprintTitle;

  /// No description provided for @footprintNoMuseum.
  ///
  /// In en, this message translates to:
  /// **'Unknown venue'**
  String get footprintNoMuseum;

  /// No description provided for @noFootprints.
  ///
  /// In en, this message translates to:
  /// **'No footprints yet'**
  String get noFootprints;

  /// No description provided for @footprintStat.
  ///
  /// In en, this message translates to:
  /// **'{count} works · {days} days'**
  String footprintStat(Object count, Object days);

  /// No description provided for @footprintLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load footprints'**
  String get footprintLoadFailed;

  /// No description provided for @footprintEmptyHint.
  ///
  /// In en, this message translates to:
  /// **'Works you recognize are recorded here automatically'**
  String get footprintEmptyHint;

  /// No description provided for @footprintGoRecognize.
  ///
  /// In en, this message translates to:
  /// **'Recognize your first work'**
  String get footprintGoRecognize;

  /// No description provided for @itemsCount.
  ///
  /// In en, this message translates to:
  /// **'{count} works'**
  String itemsCount(Object count);

  /// No description provided for @today.
  ///
  /// In en, this message translates to:
  /// **'Today'**
  String get today;

  /// No description provided for @yesterday.
  ///
  /// In en, this message translates to:
  /// **'Yesterday'**
  String get yesterday;

  /// No description provided for @dateMonthDay.
  ///
  /// In en, this message translates to:
  /// **'{month}/{day}'**
  String dateMonthDay(Object month, Object day);

  /// No description provided for @dateYearMonthDay.
  ///
  /// In en, this message translates to:
  /// **'{month}/{day}/{year}'**
  String dateYearMonthDay(Object day, Object month, Object year);

  /// No description provided for @deleteFootprintQ.
  ///
  /// In en, this message translates to:
  /// **'Delete this footprint?'**
  String get deleteFootprintQ;

  /// No description provided for @settingsTitle.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settingsTitle;

  /// No description provided for @secGeneral.
  ///
  /// In en, this message translates to:
  /// **'General'**
  String get secGeneral;

  /// No description provided for @guideLanguage.
  ///
  /// In en, this message translates to:
  /// **'Guide language'**
  String get guideLanguage;

  /// No description provided for @offlinePacks.
  ///
  /// In en, this message translates to:
  /// **'Offline museum packs'**
  String get offlinePacks;

  /// No description provided for @autoSavePhoto.
  ///
  /// In en, this message translates to:
  /// **'Auto-save photos'**
  String get autoSavePhoto;

  /// No description provided for @autoSavePhotoNeedsAccess.
  ///
  /// In en, this message translates to:
  /// **'Photo library access is needed to save photos'**
  String get autoSavePhotoNeedsAccess;

  /// No description provided for @ttsVoice.
  ///
  /// In en, this message translates to:
  /// **'TTS voice'**
  String get ttsVoice;

  /// No description provided for @ttsVoiceValue.
  ///
  /// In en, this message translates to:
  /// **'Calm · Female'**
  String get ttsVoiceValue;

  /// No description provided for @ttsVoiceSelect.
  ///
  /// In en, this message translates to:
  /// **'Choose voice'**
  String get ttsVoiceSelect;

  /// No description provided for @secAccount.
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get secAccount;

  /// No description provided for @secSupport.
  ///
  /// In en, this message translates to:
  /// **'Support & Legal'**
  String get secSupport;

  /// No description provided for @encourageUs.
  ///
  /// In en, this message translates to:
  /// **'Encourage us'**
  String get encourageUs;

  /// No description provided for @appStoreRating.
  ///
  /// In en, this message translates to:
  /// **'App Store rating'**
  String get appStoreRating;

  /// No description provided for @privacyPolicy.
  ///
  /// In en, this message translates to:
  /// **'Privacy policy'**
  String get privacyPolicy;

  /// No description provided for @freeQuota.
  ///
  /// In en, this message translates to:
  /// **'Free scan quota'**
  String get freeQuota;

  /// No description provided for @quotaValue.
  ///
  /// In en, this message translates to:
  /// **'{remain} / {total} left'**
  String quotaValue(Object remain, Object total);

  /// No description provided for @upgrade.
  ///
  /// In en, this message translates to:
  /// **'Upgrade'**
  String get upgrade;

  /// No description provided for @loginBind.
  ///
  /// In en, this message translates to:
  /// **'Sign in / Link account'**
  String get loginBind;

  /// No description provided for @notLoggedIn.
  ///
  /// In en, this message translates to:
  /// **'Not signed in'**
  String get notLoggedIn;

  /// No description provided for @userDefault.
  ///
  /// In en, this message translates to:
  /// **'User'**
  String get userDefault;

  /// No description provided for @guestPrefix.
  ///
  /// In en, this message translates to:
  /// **'Guest_'**
  String get guestPrefix;

  /// No description provided for @noEmailBound.
  ///
  /// In en, this message translates to:
  /// **'No email linked'**
  String get noEmailBound;

  /// No description provided for @logout.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get logout;

  /// No description provided for @deleteAccount.
  ///
  /// In en, this message translates to:
  /// **'Delete account'**
  String get deleteAccount;

  /// No description provided for @loadingShort.
  ///
  /// In en, this message translates to:
  /// **'Loading…'**
  String get loadingShort;

  /// No description provided for @appearance.
  ///
  /// In en, this message translates to:
  /// **'Appearance'**
  String get appearance;

  /// No description provided for @themeLight.
  ///
  /// In en, this message translates to:
  /// **'Light'**
  String get themeLight;

  /// No description provided for @themeDark.
  ///
  /// In en, this message translates to:
  /// **'Dark'**
  String get themeDark;

  /// No description provided for @themeSystem.
  ///
  /// In en, this message translates to:
  /// **'System'**
  String get themeSystem;

  /// No description provided for @featureComingSoon.
  ///
  /// In en, this message translates to:
  /// **'{feature} is coming soon'**
  String featureComingSoon(String feature);

  /// No description provided for @privacyBody.
  ///
  /// In en, this message translates to:
  /// **'Original photos are not uploaded by default and recognition data is processed temporarily only. You can delete your account and data any time under Settings → Delete account.'**
  String get privacyBody;

  /// No description provided for @privacyFullPolicy.
  ///
  /// In en, this message translates to:
  /// **'Full privacy policy'**
  String get privacyFullPolicy;

  /// No description provided for @privacyCopyLink.
  ///
  /// In en, this message translates to:
  /// **'Copy link'**
  String get privacyCopyLink;

  /// No description provided for @privacyLinkCopied.
  ///
  /// In en, this message translates to:
  /// **'Link copied'**
  String get privacyLinkCopied;

  /// No description provided for @deleteAccountQ.
  ///
  /// In en, this message translates to:
  /// **'Permanently delete account?'**
  String get deleteAccountQ;

  /// No description provided for @deleteAccountBody.
  ///
  /// In en, this message translates to:
  /// **'This will delete your account profile and remaining quota. This action cannot be undone.'**
  String get deleteAccountBody;

  /// No description provided for @deleteAccountBodyPass.
  ///
  /// In en, this message translates to:
  /// **'Any pass you bought is voided immediately and cannot be recovered — not even by signing up again. You would have to buy it anew.'**
  String get deleteAccountBodyPass;

  /// No description provided for @permanentDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete permanently'**
  String get permanentDelete;

  /// No description provided for @deleteFailed.
  ///
  /// In en, this message translates to:
  /// **'Delete failed, please try again later'**
  String get deleteFailed;

  /// No description provided for @confirmLogout.
  ///
  /// In en, this message translates to:
  /// **'Confirm sign out'**
  String get confirmLogout;

  /// No description provided for @confirmLogoutBody.
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to sign out?'**
  String get confirmLogoutBody;

  /// No description provided for @confirmYes.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirmYes;

  /// No description provided for @authEmailHint.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get authEmailHint;

  /// No description provided for @authEmailRequired.
  ///
  /// In en, this message translates to:
  /// **'Please enter your email'**
  String get authEmailRequired;

  /// No description provided for @authEmailInvalid.
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid email'**
  String get authEmailInvalid;

  /// No description provided for @authPasswordHint.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get authPasswordHint;

  /// No description provided for @authPasswordRequired.
  ///
  /// In en, this message translates to:
  /// **'Please enter your password'**
  String get authPasswordRequired;

  /// No description provided for @authPasswordMin6.
  ///
  /// In en, this message translates to:
  /// **'Password must be at least 6 characters'**
  String get authPasswordMin6;

  /// No description provided for @authConfirmPasswordHint.
  ///
  /// In en, this message translates to:
  /// **'Confirm password'**
  String get authConfirmPasswordHint;

  /// No description provided for @authPasswordMismatch.
  ///
  /// In en, this message translates to:
  /// **'Passwords do not match'**
  String get authPasswordMismatch;

  /// No description provided for @authUsernameOptionalHint.
  ///
  /// In en, this message translates to:
  /// **'Username (optional)'**
  String get authUsernameOptionalHint;

  /// No description provided for @authLoginButton.
  ///
  /// In en, this message translates to:
  /// **'Log In'**
  String get authLoginButton;

  /// No description provided for @authRegisterButton.
  ///
  /// In en, this message translates to:
  /// **'Sign Up'**
  String get authRegisterButton;

  /// No description provided for @authForgotPassword.
  ///
  /// In en, this message translates to:
  /// **'Forgot your password?'**
  String get authForgotPassword;

  /// No description provided for @authResetTitle.
  ///
  /// In en, this message translates to:
  /// **'Reset password'**
  String get authResetTitle;

  /// No description provided for @authResetPrompt.
  ///
  /// In en, this message translates to:
  /// **'Enter the email you signed up with. We\'ll send a link for setting a new password.'**
  String get authResetPrompt;

  /// No description provided for @authResetSend.
  ///
  /// In en, this message translates to:
  /// **'Send link'**
  String get authResetSend;

  /// No description provided for @authResetSent.
  ///
  /// In en, this message translates to:
  /// **'If that email is registered, the link is on its way. Check your inbox, and your spam folder.'**
  String get authResetSent;

  /// No description provided for @authResetFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t send the email. Please try again in a moment.'**
  String get authResetFailed;

  /// No description provided for @authNoAccount.
  ///
  /// In en, this message translates to:
  /// **'No account? Sign up'**
  String get authNoAccount;

  /// No description provided for @authHaveAccount.
  ///
  /// In en, this message translates to:
  /// **'Have an account? Log in'**
  String get authHaveAccount;

  /// No description provided for @authCreateAccount.
  ///
  /// In en, this message translates to:
  /// **'Create account'**
  String get authCreateAccount;

  /// No description provided for @authOrWithEmail.
  ///
  /// In en, this message translates to:
  /// **'Or with email'**
  String get authOrWithEmail;

  /// No description provided for @authGoogleLogin.
  ///
  /// In en, this message translates to:
  /// **'Sign in with Google'**
  String get authGoogleLogin;

  /// No description provided for @authAppleLogin.
  ///
  /// In en, this message translates to:
  /// **'Sign in with Apple'**
  String get authAppleLogin;

  /// No description provided for @authOr.
  ///
  /// In en, this message translates to:
  /// **'Or'**
  String get authOr;

  /// No description provided for @authGuestLogin.
  ///
  /// In en, this message translates to:
  /// **'Continue as guest'**
  String get authGuestLogin;

  /// No description provided for @authLoginFailed.
  ///
  /// In en, this message translates to:
  /// **'Login failed, check your email and password'**
  String get authLoginFailed;

  /// No description provided for @authRegisterFailed.
  ///
  /// In en, this message translates to:
  /// **'Registration failed, email may already be in use'**
  String get authRegisterFailed;

  /// No description provided for @authGoogleCancelled.
  ///
  /// In en, this message translates to:
  /// **'Google sign-in cancelled'**
  String get authGoogleCancelled;

  /// No description provided for @authGoogleFailed.
  ///
  /// In en, this message translates to:
  /// **'Google sign-in failed, please try again'**
  String get authGoogleFailed;

  /// No description provided for @authGoogleError.
  ///
  /// In en, this message translates to:
  /// **'Google sign-in error'**
  String get authGoogleError;

  /// No description provided for @authGoogleNotConfigured.
  ///
  /// In en, this message translates to:
  /// **'Google sign-in not configured, contact the administrator'**
  String get authGoogleNotConfigured;

  /// No description provided for @authGoogleNetworkError.
  ///
  /// In en, this message translates to:
  /// **'Google sign-in network error, check your connection'**
  String get authGoogleNetworkError;

  /// No description provided for @authAppleOnlyApple.
  ///
  /// In en, this message translates to:
  /// **'Apple sign-in is only supported on iOS and macOS'**
  String get authAppleOnlyApple;

  /// No description provided for @authAppleCancelled.
  ///
  /// In en, this message translates to:
  /// **'Apple sign-in cancelled'**
  String get authAppleCancelled;

  /// No description provided for @authAppleFailed.
  ///
  /// In en, this message translates to:
  /// **'Apple sign-in failed, please try again'**
  String get authAppleFailed;

  /// No description provided for @authAppleError.
  ///
  /// In en, this message translates to:
  /// **'Apple sign-in error'**
  String get authAppleError;

  /// No description provided for @authAppleNotConfigured.
  ///
  /// In en, this message translates to:
  /// **'Apple sign-in not configured'**
  String get authAppleNotConfigured;

  /// No description provided for @authGuestFailed.
  ///
  /// In en, this message translates to:
  /// **'Guest sign-in failed, please try again'**
  String get authGuestFailed;

  /// No description provided for @authGuestError.
  ///
  /// In en, this message translates to:
  /// **'Guest sign-in error'**
  String get authGuestError;

  /// No description provided for @recCandidatesTitle.
  ///
  /// In en, this message translates to:
  /// **'Is this the one?'**
  String get recCandidatesTitle;

  /// No description provided for @recNoneOfThese.
  ///
  /// In en, this message translates to:
  /// **'None of these'**
  String get recNoneOfThese;

  /// No description provided for @recNotRecognized.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t recognize this work'**
  String get recNotRecognized;

  /// No description provided for @recLabelSeen.
  ///
  /// In en, this message translates to:
  /// **'The label reads \"{text}\" — we haven\'t added its full guide yet, but we\'ve noted your request ✅'**
  String recLabelSeen(String text);

  /// No description provided for @recShootLabelBtn.
  ///
  /// In en, this message translates to:
  /// **'Photograph the wall label'**
  String get recShootLabelBtn;

  /// No description provided for @recSearchWithLabel.
  ///
  /// In en, this message translates to:
  /// **'Search using this text'**
  String get recSearchWithLabel;

  /// No description provided for @recShootLabelHint.
  ///
  /// In en, this message translates to:
  /// **'Museum labels show the title and artist — snap it and we can identify the work'**
  String get recShootLabelHint;

  /// No description provided for @recViewfinderLabelHint.
  ///
  /// In en, this message translates to:
  /// **'Aim at the label text, fill the frame'**
  String get recViewfinderLabelHint;

  /// No description provided for @camRecognizeTitle.
  ///
  /// In en, this message translates to:
  /// **'Identify Artwork'**
  String get camRecognizeTitle;

  /// No description provided for @camViewfinderHint.
  ///
  /// In en, this message translates to:
  /// **'Fit the whole artwork in the frame'**
  String get camViewfinderHint;

  /// No description provided for @camRecentGallery.
  ///
  /// In en, this message translates to:
  /// **'Recent'**
  String get camRecentGallery;

  /// No description provided for @camAllAlbums.
  ///
  /// In en, this message translates to:
  /// **'All albums'**
  String get camAllAlbums;

  /// No description provided for @camGallery.
  ///
  /// In en, this message translates to:
  /// **'Gallery'**
  String get camGallery;

  /// No description provided for @camSearch.
  ///
  /// In en, this message translates to:
  /// **'Search'**
  String get camSearch;

  /// No description provided for @guideUnavailable.
  ///
  /// In en, this message translates to:
  /// **'This artwork has too little material for a guide'**
  String get guideUnavailable;

  /// No description provided for @guideNotGenerated.
  ///
  /// In en, this message translates to:
  /// **'Guide not generated yet'**
  String get guideNotGenerated;

  /// No description provided for @audioNotReady.
  ///
  /// In en, this message translates to:
  /// **'Audio available once the guide is ready'**
  String get audioNotReady;

  /// No description provided for @audioFailed.
  ///
  /// In en, this message translates to:
  /// **'Audio unavailable, please retry'**
  String get audioFailed;

  /// No description provided for @deepGenerating.
  ///
  /// In en, this message translates to:
  /// **'Generating in-depth content…'**
  String get deepGenerating;

  /// No description provided for @camNoCamera.
  ///
  /// In en, this message translates to:
  /// **'No available camera found'**
  String get camNoCamera;

  /// No description provided for @camInitFailed.
  ///
  /// In en, this message translates to:
  /// **'Camera initialization failed'**
  String get camInitFailed;

  /// No description provided for @camTagSearch.
  ///
  /// In en, this message translates to:
  /// **'Label lookup'**
  String get camTagSearch;

  /// No description provided for @camTagHint.
  ///
  /// In en, this message translates to:
  /// **'In no-photo areas, enter the label number, title or artist'**
  String get camTagHint;

  /// No description provided for @camTagExample.
  ///
  /// In en, this message translates to:
  /// **'e.g. INV 3692 / The Bedroom'**
  String get camTagExample;

  /// No description provided for @camPackComingSoon.
  ///
  /// In en, this message translates to:
  /// **'Collection lookup opens after offline packs are available'**
  String get camPackComingSoon;

  /// No description provided for @camQuotaUsedUp.
  ///
  /// In en, this message translates to:
  /// **'Free scans used up'**
  String get camQuotaUsedUp;

  /// No description provided for @camUpgradeHint.
  ///
  /// In en, this message translates to:
  /// **'Upgrade to keep listening across the museum'**
  String get camUpgradeHint;

  /// No description provided for @camViewUpgrade.
  ///
  /// In en, this message translates to:
  /// **'View upgrade plans'**
  String get camViewUpgrade;

  /// No description provided for @camCantPhoto.
  ///
  /// In en, this message translates to:
  /// **'Can\'t take a photo? Enter the label number'**
  String get camCantPhoto;

  /// No description provided for @camRecognizing.
  ///
  /// In en, this message translates to:
  /// **'Recognizing…'**
  String get camRecognizing;

  /// No description provided for @camComparing.
  ///
  /// In en, this message translates to:
  /// **'AI is comparing with collections and public art databases'**
  String get camComparing;

  /// No description provided for @camConfirmPrompt.
  ///
  /// In en, this message translates to:
  /// **'Recognition done, please confirm the work'**
  String get camConfirmPrompt;

  /// No description provided for @camConfidence.
  ///
  /// In en, this message translates to:
  /// **'Confidence'**
  String get camConfidence;

  /// No description provided for @camConfirmStart.
  ///
  /// In en, this message translates to:
  /// **'Confirm & start guide'**
  String get camConfirmStart;

  /// No description provided for @camNoneSearch.
  ///
  /// In en, this message translates to:
  /// **'None of these? Search by title or label number →'**
  String get camNoneSearch;

  /// No description provided for @camRecognizeFailed.
  ///
  /// In en, this message translates to:
  /// **'Recognition failed'**
  String get camRecognizeFailed;

  /// No description provided for @camRetake.
  ///
  /// In en, this message translates to:
  /// **'Retake'**
  String get camRetake;

  /// No description provided for @museumCoverTab.
  ///
  /// In en, this message translates to:
  /// **'Cover'**
  String get museumCoverTab;

  /// No description provided for @museumCollectionTab.
  ///
  /// In en, this message translates to:
  /// **'Collection'**
  String get museumCollectionTab;

  /// No description provided for @museumOpeningHours.
  ///
  /// In en, this message translates to:
  /// **'Opening Hours'**
  String get museumOpeningHours;

  /// No description provided for @museumOfficialSite.
  ///
  /// In en, this message translates to:
  /// **'Official Website'**
  String get museumOfficialSite;

  /// No description provided for @museumIntroComingSoon.
  ///
  /// In en, this message translates to:
  /// **'Museum introduction coming soon'**
  String get museumIntroComingSoon;

  /// No description provided for @paywallTitle.
  ///
  /// In en, this message translates to:
  /// **'Paris 7-Day Pass'**
  String get paywallTitle;

  /// No description provided for @paywallPitch.
  ///
  /// In en, this message translates to:
  /// **'Unlimited photo recognition and full audio commentary across the Louvre, Orsay, the Orangerie and the Petit Palais.'**
  String get paywallPitch;

  /// No description provided for @paywallFreeAlways.
  ///
  /// In en, this message translates to:
  /// **'Browsing, search and full written commentary are always free.'**
  String get paywallFreeAlways;

  /// No description provided for @paywallBuy.
  ///
  /// In en, this message translates to:
  /// **'Get the pass'**
  String get paywallBuy;

  /// No description provided for @paywallRestore.
  ///
  /// In en, this message translates to:
  /// **'Paid but no pass?'**
  String get paywallRestore;

  /// No description provided for @restoreInProgress.
  ///
  /// In en, this message translates to:
  /// **'Restoring…'**
  String get restoreInProgress;

  /// No description provided for @restoreNothingFound.
  ///
  /// In en, this message translates to:
  /// **'No incomplete payment found'**
  String get restoreNothingFound;

  /// No description provided for @restoreSucceeded.
  ///
  /// In en, this message translates to:
  /// **'Your pass has been restored'**
  String get restoreSucceeded;

  /// No description provided for @audioFreePreview.
  ///
  /// In en, this message translates to:
  /// **'Free preview'**
  String get audioFreePreview;

  /// No description provided for @audioLockedHint.
  ///
  /// In en, this message translates to:
  /// **'Audio commentary needs the pass — artworks you\'ve scanned are free to listen to.'**
  String get audioLockedHint;

  /// No description provided for @quotaExhausted.
  ///
  /// In en, this message translates to:
  /// **'You\'ve used all your free recognitions.'**
  String get quotaExhausted;

  /// No description provided for @activateLater.
  ///
  /// In en, this message translates to:
  /// **'Later'**
  String get activateLater;

  /// No description provided for @paywallLoginToBuy.
  ///
  /// In en, this message translates to:
  /// **'Sign in to buy'**
  String get paywallLoginToBuy;

  /// No description provided for @paywallLoginWhy.
  ///
  /// In en, this message translates to:
  /// **'Your pass is tied to your account, so you keep it on a new phone.'**
  String get paywallLoginWhy;

  /// No description provided for @passActive.
  ///
  /// In en, this message translates to:
  /// **'Pass active'**
  String get passActive;

  /// No description provided for @passExpiresOn.
  ///
  /// In en, this message translates to:
  /// **'Expires {date}'**
  String passExpiresOn(DateTime date);

  /// No description provided for @passPendingActivation.
  ///
  /// In en, this message translates to:
  /// **'Purchased · not activated'**
  String get passPendingActivation;

  /// No description provided for @passActivateHint.
  ///
  /// In en, this message translates to:
  /// **'Starts when you first play a guide'**
  String get passActivateHint;

  /// No description provided for @viewBenefits.
  ///
  /// In en, this message translates to:
  /// **'View benefits'**
  String get viewBenefits;

  /// No description provided for @unlimited.
  ///
  /// In en, this message translates to:
  /// **'Unlimited'**
  String get unlimited;

  /// No description provided for @paywallPriceNote.
  ///
  /// In en, this message translates to:
  /// **'One-time · not a subscription'**
  String get paywallPriceNote;

  /// No description provided for @paywallClockHead.
  ///
  /// In en, this message translates to:
  /// **'The clock doesn\'t start at purchase'**
  String get paywallClockHead;

  /// No description provided for @paywallClockBody.
  ///
  /// In en, this message translates to:
  /// **'Your 7 days begin the first time you use a premium feature and confirm. Buy ahead, start at the museum.'**
  String get paywallClockBody;

  /// Paywall: unactivated passes expire. Required disclosure — the backend really does forfeit them (ACTIVATION_WINDOW), so this line must ship with it.
  ///
  /// In en, this message translates to:
  /// **'An unactivated pass lapses 30 days after purchase.'**
  String get paywallLapseNote;

  /// No description provided for @ticketStub.
  ///
  /// In en, this message translates to:
  /// **'Stub'**
  String get ticketStub;

  /// No description provided for @ticketStubPending.
  ///
  /// In en, this message translates to:
  /// **'expiry to be filled'**
  String get ticketStubPending;

  /// No description provided for @ticketStubUntorn.
  ///
  /// In en, this message translates to:
  /// **'not torn'**
  String get ticketStubUntorn;

  /// No description provided for @ticketValidUntil.
  ///
  /// In en, this message translates to:
  /// **'Valid until'**
  String get ticketValidUntil;

  /// No description provided for @ticketDateTime.
  ///
  /// In en, this message translates to:
  /// **'{date} {time}'**
  String ticketDateTime(DateTime date, DateTime time);

  /// No description provided for @ticketDaysLeft.
  ///
  /// In en, this message translates to:
  /// **'{days} days left'**
  String ticketDaysLeft(int days);

  /// No description provided for @activateSheetTitle.
  ///
  /// In en, this message translates to:
  /// **'Start your 7 days now?'**
  String get activateSheetTitle;

  /// No description provided for @activateSheetBody.
  ///
  /// In en, this message translates to:
  /// **'The clock starts on confirm and ends {date} {time}. This can\'t be undone.'**
  String activateSheetBody(DateTime date, DateTime time);

  /// No description provided for @activateTear.
  ///
  /// In en, this message translates to:
  /// **'Tear it, start now'**
  String get activateTear;

  /// No description provided for @activateWaiting.
  ///
  /// In en, this message translates to:
  /// **'Confirming…'**
  String get activateWaiting;

  /// No description provided for @activateWaitingNote.
  ///
  /// In en, this message translates to:
  /// **'The ticket isn\'t torn yet — it starts once confirmed'**
  String get activateWaitingNote;

  /// No description provided for @activateDoneTitle.
  ///
  /// In en, this message translates to:
  /// **'Your pass has started'**
  String get activateDoneTitle;

  /// No description provided for @activateDoneBody.
  ///
  /// In en, this message translates to:
  /// **'Audio commentary at all four museums and unlimited recognition are unlocked.'**
  String get activateDoneBody;

  /// No description provided for @activateDoneCta.
  ///
  /// In en, this message translates to:
  /// **'Continue'**
  String get activateDoneCta;

  /// No description provided for @activateFailTitle.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t confirm — your ticket wasn\'t used'**
  String get activateFailTitle;

  /// No description provided for @activateFailBody.
  ///
  /// In en, this message translates to:
  /// **'No connection, so the 7 days haven\'t started. Your pass is still intact; try again.'**
  String get activateFailBody;

  /// No description provided for @activateRetry.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get activateRetry;

  /// No description provided for @benefitsMyPass.
  ///
  /// In en, this message translates to:
  /// **'My pass'**
  String get benefitsMyPass;

  /// No description provided for @benefitsSecFreeQuota.
  ///
  /// In en, this message translates to:
  /// **'Free allowance'**
  String get benefitsSecFreeQuota;

  /// No description provided for @benefitsSecFeatures.
  ///
  /// In en, this message translates to:
  /// **'Features'**
  String get benefitsSecFeatures;

  /// No description provided for @benefitsSecBuyable.
  ///
  /// In en, this message translates to:
  /// **'Available'**
  String get benefitsSecBuyable;

  /// No description provided for @benefitsSecIncluded.
  ///
  /// In en, this message translates to:
  /// **'Included'**
  String get benefitsSecIncluded;

  /// No description provided for @benefitsSecUnlocked.
  ///
  /// In en, this message translates to:
  /// **'Unlocked'**
  String get benefitsSecUnlocked;

  /// No description provided for @benefitsSecPurchases.
  ///
  /// In en, this message translates to:
  /// **'Purchases'**
  String get benefitsSecPurchases;

  /// No description provided for @benefitsSecCurrentQuota.
  ///
  /// In en, this message translates to:
  /// **'Your allowance now'**
  String get benefitsSecCurrentQuota;

  /// No description provided for @benefitsSecBuyAnother.
  ///
  /// In en, this message translates to:
  /// **'Another pass'**
  String get benefitsSecBuyAnother;

  /// No description provided for @benefitsRecognition.
  ///
  /// In en, this message translates to:
  /// **'Photo recognition'**
  String get benefitsRecognition;

  /// No description provided for @benefitsFreeAudioNote.
  ///
  /// In en, this message translates to:
  /// **'For every artwork you scan, the main audio commentary is free. Any other artwork can be unlocked with one free credit.'**
  String get benefitsFreeAudioNote;

  /// No description provided for @benefitsFeatBrowse.
  ///
  /// In en, this message translates to:
  /// **'Browsing, search, full written commentary'**
  String get benefitsFeatBrowse;

  /// No description provided for @benefitsFeatPresetQa.
  ///
  /// In en, this message translates to:
  /// **'Suggested questions answered'**
  String get benefitsFeatPresetQa;

  /// No description provided for @benefitsFeatRecognition.
  ///
  /// In en, this message translates to:
  /// **'Unlimited photo recognition'**
  String get benefitsFeatRecognition;

  /// No description provided for @benefitsFeatAllAudio.
  ///
  /// In en, this message translates to:
  /// **'Audio commentary across all four museums'**
  String get benefitsFeatAllAudio;

  /// No description provided for @benefitsFeatDeepAudio.
  ///
  /// In en, this message translates to:
  /// **'Audio for in-depth sections'**
  String get benefitsFeatDeepAudio;

  /// No description provided for @benefitsNeedsPass.
  ///
  /// In en, this message translates to:
  /// **'Pass needed'**
  String get benefitsNeedsPass;

  /// No description provided for @benefitsNotStartedHead.
  ///
  /// In en, this message translates to:
  /// **'The clock hasn\'t started'**
  String get benefitsNotStartedHead;

  /// No description provided for @benefitsNotStartedBody.
  ///
  /// In en, this message translates to:
  /// **'The first time you use audio commentary or recognition at the museum, we\'ll ask you to confirm. Your 7 days start from that moment.'**
  String get benefitsNotStartedBody;

  /// No description provided for @benefitsMuseums.
  ///
  /// In en, this message translates to:
  /// **'Louvre · Orsay · Orangerie · Petit Palais'**
  String get benefitsMuseums;

  /// No description provided for @benefitsStartNow.
  ///
  /// In en, this message translates to:
  /// **'Start my 7 days now'**
  String get benefitsStartNow;

  /// No description provided for @benefitsStartNowNote.
  ///
  /// In en, this message translates to:
  /// **'If you\'re not at the museum yet, it\'s better to wait'**
  String get benefitsStartNowNote;

  /// No description provided for @benefitsExpiredBody.
  ///
  /// In en, this message translates to:
  /// **'Your 7 days are up. Your free allowance is back, and written commentary is still complete.'**
  String get benefitsExpiredBody;

  /// Benefits page: the previous pass, already used up.
  ///
  /// In en, this message translates to:
  /// **'Previous pass used up · {start} – {end}'**
  String benefitsPrevPass(DateTime start, DateTime end);

  /// No description provided for @benefitsEndedAt.
  ///
  /// In en, this message translates to:
  /// **'Ended'**
  String get benefitsEndedAt;

  /// No description provided for @benefitsLapsedHead.
  ///
  /// In en, this message translates to:
  /// **'This pass was never started'**
  String get benefitsLapsedHead;

  /// No description provided for @benefitsLapsedBody.
  ///
  /// In en, this message translates to:
  /// **'It was not used within 30 days of purchase, so it has expired. Your free quota is back, and full text guides remain available.'**
  String get benefitsLapsedBody;

  /// No description provided for @benefitsBoughtOn.
  ///
  /// In en, this message translates to:
  /// **'Purchased'**
  String get benefitsBoughtOn;

  /// Benefits page: purchase record date.
  ///
  /// In en, this message translates to:
  /// **'{date}'**
  String benefitsDateOnly(DateTime date);

  /// No description provided for @edgeUnknownHead.
  ///
  /// In en, this message translates to:
  /// **'Can\'t read your pass right now'**
  String get edgeUnknownHead;

  /// No description provided for @edgeUnknownBody.
  ///
  /// In en, this message translates to:
  /// **'There\'s no connection, so we can\'t confirm whether you already have a pass — or start a purchase safely.'**
  String get edgeUnknownBody;

  /// No description provided for @edgeUnknownNote.
  ///
  /// In en, this message translates to:
  /// **'If you\'ve already bought one, it comes back automatically once you\'re online. You won\'t be charged twice.'**
  String get edgeUnknownNote;

  /// No description provided for @edgeSignedOutHead.
  ///
  /// In en, this message translates to:
  /// **'The pass belongs to an account'**
  String get edgeSignedOutHead;

  /// No description provided for @edgeSignedOutBody.
  ///
  /// In en, this message translates to:
  /// **'Sign in before buying and it survives a new phone or a reinstall.'**
  String get edgeSignedOutBody;

  /// No description provided for @edgeConflictTitle.
  ///
  /// In en, this message translates to:
  /// **'This pass is tied to another account'**
  String get edgeConflictTitle;

  /// No description provided for @edgeConflictBody.
  ///
  /// In en, this message translates to:
  /// **'This purchase belongs to a different GoMuseum account. One pass can\'t serve two accounts, so it can\'t be restored here.'**
  String get edgeConflictBody;

  /// No description provided for @edgeConflictBound.
  ///
  /// In en, this message translates to:
  /// **'Tied to'**
  String get edgeConflictBound;

  /// No description provided for @edgeConflictOther.
  ///
  /// In en, this message translates to:
  /// **'another account'**
  String get edgeConflictOther;

  /// No description provided for @edgeConflictHelp.
  ///
  /// In en, this message translates to:
  /// **'Sign in with the account you bought it on. If you\'re not sure which one, or you think this is a mistake, get in touch and we can look it up.'**
  String get edgeConflictHelp;

  /// No description provided for @edgeSwitchAccount.
  ///
  /// In en, this message translates to:
  /// **'Switch account'**
  String get edgeSwitchAccount;

  /// No description provided for @edgeContactSupport.
  ///
  /// In en, this message translates to:
  /// **'Contact us'**
  String get edgeContactSupport;

  /// No description provided for @drawerLockedHint.
  ///
  /// In en, this message translates to:
  /// **'Audio for in-depth sections needs the pass. All the text is free.'**
  String get drawerLockedHint;

  /// No description provided for @drawerLockedCta.
  ///
  /// In en, this message translates to:
  /// **'See the pass'**
  String get drawerLockedCta;

  /// No description provided for @purchaseSuccess.
  ///
  /// In en, this message translates to:
  /// **'Purchased. Your pass is ready.'**
  String get purchaseSuccess;

  /// No description provided for @purchaseVerifyPending.
  ///
  /// In en, this message translates to:
  /// **'We couldn\'t confirm the purchase yet. Reopening the app will retry.'**
  String get purchaseVerifyPending;

  /// No description provided for @purchaseFailed.
  ///
  /// In en, this message translates to:
  /// **'The purchase didn\'t go through. Please try again.'**
  String get purchaseFailed;

  /// No description provided for @ticketPaid.
  ///
  /// In en, this message translates to:
  /// **'Paid'**
  String get ticketPaid;

  /// No description provided for @ticketVoid.
  ///
  /// In en, this message translates to:
  /// **'EXPIRED'**
  String get ticketVoid;

  /// Toast after copying the support email on the receipt-conflict screen.
  ///
  /// In en, this message translates to:
  /// **'Support address copied: {email}'**
  String edgeSupportCopied(String email);

  /// No description provided for @fbTitleObject.
  ///
  /// In en, this message translates to:
  /// **'Report an issue'**
  String get fbTitleObject;

  /// No description provided for @fbTitleApp.
  ///
  /// In en, this message translates to:
  /// **'Feedback'**
  String get fbTitleApp;

  /// No description provided for @fbContentWrong.
  ///
  /// In en, this message translates to:
  /// **'Wrong content'**
  String get fbContentWrong;

  /// No description provided for @fbAudioBad.
  ///
  /// In en, this message translates to:
  /// **'Odd pronunciation'**
  String get fbAudioBad;

  /// No description provided for @fbAudioMissing.
  ///
  /// In en, this message translates to:
  /// **'No audio'**
  String get fbAudioMissing;

  /// No description provided for @fbAppCrash.
  ///
  /// In en, this message translates to:
  /// **'Crashes or lag'**
  String get fbAppCrash;

  /// No description provided for @fbRecognitionBad.
  ///
  /// In en, this message translates to:
  /// **'Poor recognition'**
  String get fbRecognitionBad;

  /// No description provided for @fbFeatureRequest.
  ///
  /// In en, this message translates to:
  /// **'Feature request'**
  String get fbFeatureRequest;

  /// No description provided for @fbOther.
  ///
  /// In en, this message translates to:
  /// **'Something else'**
  String get fbOther;

  /// No description provided for @fbTextHint.
  ///
  /// In en, this message translates to:
  /// **'Anything else? (optional — please don\'t include personal information)'**
  String get fbTextHint;

  /// No description provided for @fbSubmit.
  ///
  /// In en, this message translates to:
  /// **'Submit'**
  String get fbSubmit;

  /// No description provided for @fbThanks.
  ///
  /// In en, this message translates to:
  /// **'Thanks — we got it'**
  String get fbThanks;

  /// No description provided for @fbFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t send. Check your connection.'**
  String get fbFailed;

  /// No description provided for @fbRetry.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get fbRetry;

  /// No description provided for @unlockAudioTitle.
  ///
  /// In en, this message translates to:
  /// **'Use one free credit?'**
  String get unlockAudioTitle;

  /// No description provided for @unlockAudioBody.
  ///
  /// In en, this message translates to:
  /// **'Unlocks the audio commentary for this artwork. {left} will be left.'**
  String unlockAudioBody(int left);

  /// No description provided for @unlockAudioCta.
  ///
  /// In en, this message translates to:
  /// **'Unlock and play'**
  String get unlockAudioCta;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) => <String>[
        'de',
        'en',
        'es',
        'fr',
        'it',
        'ja',
        'ko',
        'pl',
        'zh'
      ].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when language+script codes are specified.
  switch (locale.languageCode) {
    case 'zh':
      {
        switch (locale.scriptCode) {
          case 'Hant':
            return AppLocalizationsZhHant();
        }
        break;
      }
  }

  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'de':
      return AppLocalizationsDe();
    case 'en':
      return AppLocalizationsEn();
    case 'es':
      return AppLocalizationsEs();
    case 'fr':
      return AppLocalizationsFr();
    case 'it':
      return AppLocalizationsIt();
    case 'ja':
      return AppLocalizationsJa();
    case 'ko':
      return AppLocalizationsKo();
    case 'pl':
      return AppLocalizationsPl();
    case 'zh':
      return AppLocalizationsZh();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
