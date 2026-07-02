// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class AppLocalizationsFr extends AppLocalizations {
  AppLocalizationsFr([String locale = 'fr']) : super(locale);

  @override
  String get home => 'Accueil';

  @override
  String get explore => 'Explorer';

  @override
  String get capture => 'Capturer';

  @override
  String get footprints => 'Empreintes';

  @override
  String get settings => 'Paramètres';

  @override
  String get navScan => 'Scanner';

  @override
  String get artworkRecognition => 'Reconnaissance d\'œuvre d\'art';

  @override
  String get takePhoto => 'Prendre une photo';

  @override
  String get chooseFromGallery => 'Choisir dans la galerie';

  @override
  String get selectImagePrompt =>
      'Sélectionnez une image pour reconnaître l\'œuvre d\'art';

  @override
  String get error => 'Erreur';

  @override
  String get comingSoon => 'Bientôt disponible';

  @override
  String get comingSoonShort => 'Bientôt';

  @override
  String get language => 'Langue';

  @override
  String get selectLanguage => 'Sélectionner la langue';

  @override
  String get retry => 'Réessayer';

  @override
  String get cancel => 'Annuler';

  @override
  String get delete => 'Supprimer';

  @override
  String get confirm => 'Confirmer';

  @override
  String get gotIt => 'Compris';

  @override
  String get loadFailed => 'Échec du chargement';

  @override
  String get loadFailedRetry => 'Échec du chargement, veuillez réessayer';

  @override
  String get toBeRefined => 'À compléter';

  @override
  String get viewAll => 'Tout voir →';

  @override
  String get all => 'Tout';

  @override
  String get homePocketGuide => 'Guide de musée de poche';

  @override
  String get homeSlogan =>
      'Approchez-vous d\'une œuvre,\nécoutez son histoire.';

  @override
  String get homeCtaRecognize => 'Photographier pour reconnaître & écouter';

  @override
  String homeFreeLeft(Object count) {
    return '$count scans gratuits restants · Passez à l\'offre complète';
  }

  @override
  String get homeNearby => 'Musées à proximité';

  @override
  String get statusOpen => 'Ouvert';

  @override
  String get exploreTitle => 'Explorer';

  @override
  String get searchCityMuseumArtwork => 'Rechercher villes, musées ou œuvres';

  @override
  String museumCount(Object count) {
    return '$count musées';
  }

  @override
  String get noMuseums => 'Aucun musée';

  @override
  String get noMatchedMuseums => 'Aucun musée correspondant';

  @override
  String artworkCountLabel(Object count) {
    return '$count œuvres';
  }

  @override
  String recordedCount(Object count) {
    return '$count œuvres dans la collection';
  }

  @override
  String get noArtworks => 'Aucune œuvre';

  @override
  String loadingShown(Object shown, Object total) {
    return 'Chargement · $shown/$total affichés';
  }

  @override
  String allLoaded(Object total) {
    return 'Tout chargé · $total au total';
  }

  @override
  String get guideVoiceGuide => 'Guide audio';

  @override
  String get guideGenFailed => 'Échec de la génération de l\'explication';

  @override
  String get guideWriting => 'Rédaction de votre explication…';

  @override
  String get guideHighlight => 'À retenir';

  @override
  String get guideQa => 'Q&R';

  @override
  String get guideThinking => 'Réflexion…';

  @override
  String get guideQ1 => 'Qu\'est-ce qui rend ce tableau spécial ?';

  @override
  String get guideQ2 => 'Que vivait l\'artiste à cette époque ?';

  @override
  String get guideAskHint => 'Posez une question sur ce tableau…';

  @override
  String get guideAskShort => 'Poser une question';

  @override
  String get guideVoiceComingSoon =>
      'La Q&R vocale arrive bientôt, écrivez pour l\'instant';

  @override
  String get guideGenerating => 'Génération de l\'explication…';

  @override
  String get guideEmpty => 'Pas encore d\'explication fondée (à compléter)';

  @override
  String get guideInfo => 'Informations sur l\'œuvre';

  @override
  String get guideStandardTour => 'Visite standard';

  @override
  String get guideListen => 'Écouter';

  @override
  String get guideDiveIn => 'Envie d\'en savoir plus ? Touchez';

  @override
  String get guideDeepContent => 'En détail';

  @override
  String get guideAskPlaceholder => 'Posez une question…';

  @override
  String get guideArtist => 'Artiste';

  @override
  String get guideArtistTab => 'Artiste';

  @override
  String get guideNotableWorks => 'Œuvres majeures';

  @override
  String get guideNoAnswer => '(aucune réponse renvoyée)';

  @override
  String get guideAnswerFailed =>
      'Échec de la réponse, veuillez réessayer plus tard.';

  @override
  String get factInventory => 'N° d\'inventaire';

  @override
  String get factLocation => 'Lieu de conservation';

  @override
  String get factProvenance => 'Provenance';

  @override
  String get factExhibitions => 'Expositions';

  @override
  String get factBibliography => 'Bibliographie';

  @override
  String get factArtist => 'Artiste';

  @override
  String get factNone => 'Aucune information détaillée';

  @override
  String get footprintTitle => 'Empreintes';

  @override
  String get noFootprints => 'Aucune empreinte';

  @override
  String footprintStat(Object count, Object days) {
    return '$count œuvres · $days jours';
  }

  @override
  String get footprintLoadFailed => 'Échec du chargement des empreintes';

  @override
  String get footprintEmptyHint =>
      'Les œuvres reconnues sont enregistrées ici automatiquement';

  @override
  String get footprintGoRecognize => 'Reconnaître votre première œuvre';

  @override
  String itemsCount(Object count) {
    return '$count œuvres';
  }

  @override
  String get today => 'Aujourd\'hui';

  @override
  String get yesterday => 'Hier';

  @override
  String dateMonthDay(Object month, Object day) {
    return '$day/$month';
  }

  @override
  String get deleteFootprintQ => 'Supprimer cette empreinte ?';

  @override
  String get settingsTitle => 'Paramètres';

  @override
  String get secGeneral => 'Général';

  @override
  String get guideLanguage => 'Langue du guide';

  @override
  String get offlinePacks => 'Packs de musée hors ligne';

  @override
  String get autoSavePhoto => 'Enregistrer les photos automatiquement';

  @override
  String get ttsVoice => 'Voix TTS';

  @override
  String get ttsVoiceValue => 'Posée · Femme';

  @override
  String get ttsVoiceSelect => 'Choisir la voix';

  @override
  String get secAccount => 'Compte';

  @override
  String get secSupport => 'Aide & Mentions légales';

  @override
  String get encourageUs => 'Encouragez-nous';

  @override
  String get appStoreRating => 'Note sur l\'App Store';

  @override
  String get privacyPolicy => 'Politique de confidentialité';

  @override
  String get freeQuota => 'Quota de scans gratuits';

  @override
  String quotaValue(Object remain, Object total) {
    return '$remain / $total restants';
  }

  @override
  String get upgrade => 'Améliorer';

  @override
  String get loginBind => 'Se connecter / Lier un compte';

  @override
  String get notLoggedIn => 'Non connecté';

  @override
  String get userDefault => 'Utilisateur';

  @override
  String get guestPrefix => 'Invité_';

  @override
  String get noEmailBound => 'Aucun e-mail lié';

  @override
  String get logout => 'Se déconnecter';

  @override
  String get deleteAccount => 'Supprimer le compte';

  @override
  String get loadingShort => 'Chargement…';

  @override
  String get appearance => 'Apparence';

  @override
  String get themeLight => 'Clair';

  @override
  String get themeDark => 'Sombre';

  @override
  String get themeSystem => 'Système';

  @override
  String featureComingSoon(String feature) {
    return '$feature arrive bientôt';
  }

  @override
  String get privacyBody =>
      'Les photos originales ne sont pas téléchargées par défaut ; les données de reconnaissance sont traitées temporairement. Vous pouvez supprimer votre compte et vos données à tout moment. Les conditions complètes seront fournies lors de la sortie officielle.';

  @override
  String get deleteAccountQ => 'Supprimer définitivement le compte ?';

  @override
  String get deleteAccountBody =>
      'Cela supprimera votre profil et le quota restant. Cette action est irréversible.';

  @override
  String get permanentDelete => 'Supprimer définitivement';

  @override
  String get deleteFailed =>
      'Échec de la suppression, veuillez réessayer plus tard';

  @override
  String get confirmLogout => 'Confirmer la déconnexion';

  @override
  String get confirmLogoutBody => 'Voulez-vous vraiment vous déconnecter ?';

  @override
  String get confirmYes => 'Confirmer';

  @override
  String get camNoCamera => 'Aucune caméra disponible';

  @override
  String get camInitFailed => 'Échec de l\'initialisation de la caméra';

  @override
  String get camTagSearch => 'Recherche par cartel';

  @override
  String get camTagHint =>
      'Dans les zones sans photo, saisissez le numéro de cartel, le titre ou l\'artiste';

  @override
  String get camTagExample => 'ex. INV 3692 / La Chambre';

  @override
  String get camPackComingSoon =>
      'La recherche dans la collection s\'ouvrira après l\'arrivée des packs hors ligne';

  @override
  String get camQuotaUsedUp => 'Scans gratuits épuisés';

  @override
  String get camUpgradeHint =>
      'Améliorez pour continuer à écouter dans tout le musée';

  @override
  String get camViewUpgrade => 'Voir les offres';

  @override
  String get camCantPhoto =>
      'Impossible de photographier ? Saisissez le numéro de cartel';

  @override
  String get camRecognizing => 'Reconnaissance…';

  @override
  String get camComparing =>
      'L\'IA compare avec les collections et les bases d\'art publiques';

  @override
  String get camConfirmPrompt =>
      'Reconnaissance terminée, veuillez confirmer l\'œuvre';

  @override
  String get camConfidence => 'Confiance';

  @override
  String get camConfirmStart => 'Confirmer & démarrer le guide';

  @override
  String get camNoneSearch =>
      'Aucune correspondance ? Recherchez par titre ou numéro de cartel →';

  @override
  String get camRecognizeFailed => 'Échec de la reconnaissance';

  @override
  String get camRetake => 'Reprendre';
}
