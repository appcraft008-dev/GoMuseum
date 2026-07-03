// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Spanish Castilian (`es`).
class AppLocalizationsEs extends AppLocalizations {
  AppLocalizationsEs([String locale = 'es']) : super(locale);

  @override
  String get home => 'Inicio';

  @override
  String get explore => 'Explorar';

  @override
  String get capture => 'Capturar';

  @override
  String get footprints => 'Huellas';

  @override
  String get settings => 'Ajustes';

  @override
  String get navScan => 'Escanear';

  @override
  String get artworkRecognition => 'Reconocimiento de obras';

  @override
  String get takePhoto => 'Tomar foto';

  @override
  String get chooseFromGallery => 'Elegir de la galería';

  @override
  String get selectImagePrompt =>
      'Selecciona una imagen para reconocer la obra';

  @override
  String get error => 'Error';

  @override
  String get comingSoon => 'Próximamente';

  @override
  String get comingSoonShort => 'Próximamente';

  @override
  String get language => 'Idioma';

  @override
  String get selectLanguage => 'Seleccionar idioma';

  @override
  String get retry => 'Reintentar';

  @override
  String get cancel => 'Cancelar';

  @override
  String get delete => 'Eliminar';

  @override
  String get confirm => 'Confirmar';

  @override
  String get gotIt => 'Entendido';

  @override
  String get loadFailed => 'Error al cargar';

  @override
  String get loadFailedRetry => 'Error al cargar, inténtalo de nuevo';

  @override
  String get toBeRefined => 'En progreso';

  @override
  String get viewAll => 'Ver todo →';

  @override
  String get all => 'Todo';

  @override
  String get homePocketGuide => 'Guía de museo de bolsillo';

  @override
  String get homeSlogan => 'Acércate a una obra,\nescucha su historia.';

  @override
  String get homeCtaRecognize => 'Fotografía para reconocer y escuchar';

  @override
  String homeFreeLeft(Object count) {
    return '$count escaneos gratis restantes · Mejora para acceso completo';
  }

  @override
  String get homeNearby => 'Museos cercanos';

  @override
  String get statusOpen => 'Abierto';

  @override
  String get exploreTitle => 'Explorar';

  @override
  String get searchCityMuseumArtwork => 'Buscar ciudades, museos u obras';

  @override
  String museumCount(Object count) {
    return '$count museos';
  }

  @override
  String get noMuseums => 'Aún no hay museos';

  @override
  String get noMatchedMuseums => 'No hay museos coincidentes';

  @override
  String artworkCountLabel(Object count) {
    return '$count obras';
  }

  @override
  String recordedCount(Object count) {
    return '$count obras en la colección';
  }

  @override
  String get noArtworks => 'Aún no hay obras';

  @override
  String loadingShown(Object shown, Object total) {
    return 'Cargando · $shown/$total mostradas';
  }

  @override
  String allLoaded(Object total) {
    return 'Todo cargado · $total en total';
  }

  @override
  String get guideVoiceGuide => 'Audioguía';

  @override
  String get guideGenFailed => 'Error al generar la explicación';

  @override
  String get guideWriting => 'Escribiendo tu explicación…';

  @override
  String get guideHighlight => 'Destacado';

  @override
  String get guideQa => 'Preguntas y respuestas';

  @override
  String get guideThinking => 'Pensando…';

  @override
  String get guideQ1 => '¿Qué hace especial a este cuadro?';

  @override
  String get guideQ2 => '¿Qué vivía el artista en esa época?';

  @override
  String get guideAskHint => 'Pregunta sobre este cuadro…';

  @override
  String get guideAskShort => 'Preguntar sobre este cuadro';

  @override
  String get guideVoiceComingSoon =>
      'Las preguntas por voz llegan pronto, escribe por ahora';

  @override
  String get guideGenerating => 'Generando contenido · aprox. 1–3 min';

  @override
  String get guideEmpty => 'Aún no hay explicación fundamentada (en progreso)';

  @override
  String get guideInfo => 'Información de la obra';

  @override
  String get guideStandardTour => 'Visita estándar';

  @override
  String get guideListen => 'Escuchar';

  @override
  String get guideDiveIn => '¿Quieres más? Toca abajo';

  @override
  String get guideDeepContent => 'En profundidad';

  @override
  String get guideAskPlaceholder => 'Pregunta lo que quieras…';

  @override
  String get guideArtist => 'Artista';

  @override
  String get guideArtistTab => 'Artista';

  @override
  String get guideNotableWorks => 'Obras destacadas';

  @override
  String get guideNoAnswer => '(sin respuesta)';

  @override
  String get guideAnswerFailed => 'La respuesta falló, inténtalo más tarde.';

  @override
  String get factInventory => 'N.º de inventario';

  @override
  String get factLocation => 'Ubicación';

  @override
  String get factProvenance => 'Procedencia';

  @override
  String get factExhibitions => 'Exposiciones';

  @override
  String get factBibliography => 'Bibliografía';

  @override
  String get factArtist => 'Artista';

  @override
  String get factNone => 'Sin información detallada';

  @override
  String get footprintTitle => 'Huellas';

  @override
  String get noFootprints => 'Aún no hay huellas';

  @override
  String footprintStat(Object count, Object days) {
    return '$count obras · $days días';
  }

  @override
  String get footprintLoadFailed => 'Error al cargar las huellas';

  @override
  String get footprintEmptyHint =>
      'Las obras que reconoces se guardan aquí automáticamente';

  @override
  String get footprintGoRecognize => 'Reconoce tu primera obra';

  @override
  String itemsCount(Object count) {
    return '$count obras';
  }

  @override
  String get today => 'Hoy';

  @override
  String get yesterday => 'Ayer';

  @override
  String dateMonthDay(Object month, Object day) {
    return '$day/$month';
  }

  @override
  String get deleteFootprintQ => '¿Eliminar esta huella?';

  @override
  String get settingsTitle => 'Ajustes';

  @override
  String get secGeneral => 'General';

  @override
  String get guideLanguage => 'Idioma de la guía';

  @override
  String get offlinePacks => 'Paquetes de museo sin conexión';

  @override
  String get autoSavePhoto => 'Guardar fotos automáticamente';

  @override
  String get ttsVoice => 'Voz TTS';

  @override
  String get ttsVoiceValue => 'Serena · Femenina';

  @override
  String get ttsVoiceSelect => 'Elegir voz';

  @override
  String get secAccount => 'Cuenta';

  @override
  String get secSupport => 'Soporte y aspectos legales';

  @override
  String get encourageUs => 'Anímanos';

  @override
  String get appStoreRating => 'Valoración en App Store';

  @override
  String get privacyPolicy => 'Política de privacidad';

  @override
  String get freeQuota => 'Cuota de escaneos gratis';

  @override
  String quotaValue(Object remain, Object total) {
    return '$remain / $total restantes';
  }

  @override
  String get upgrade => 'Mejorar';

  @override
  String get loginBind => 'Iniciar sesión / Vincular cuenta';

  @override
  String get notLoggedIn => 'Sin sesión iniciada';

  @override
  String get userDefault => 'Usuario';

  @override
  String get guestPrefix => 'Invitado_';

  @override
  String get noEmailBound => 'Ningún correo vinculado';

  @override
  String get logout => 'Cerrar sesión';

  @override
  String get deleteAccount => 'Eliminar cuenta';

  @override
  String get loadingShort => 'Cargando…';

  @override
  String get appearance => 'Apariencia';

  @override
  String get themeLight => 'Claro';

  @override
  String get themeDark => 'Oscuro';

  @override
  String get themeSystem => 'Sistema';

  @override
  String featureComingSoon(String feature) {
    return '$feature llega pronto';
  }

  @override
  String get privacyBody =>
      'Las fotos originales no se suben por defecto; los datos de reconocimiento se procesan solo temporalmente. Puedes eliminar tu cuenta y tus datos en cualquier momento. Los términos completos se ofrecerán en el lanzamiento oficial.';

  @override
  String get deleteAccountQ => '¿Eliminar la cuenta permanentemente?';

  @override
  String get deleteAccountBody =>
      'Esto eliminará tu perfil de cuenta y la cuota restante. Esta acción no se puede deshacer.';

  @override
  String get permanentDelete => 'Eliminar permanentemente';

  @override
  String get deleteFailed => 'Error al eliminar, inténtalo más tarde';

  @override
  String get confirmLogout => 'Confirmar cierre de sesión';

  @override
  String get confirmLogoutBody => '¿Seguro que quieres cerrar sesión?';

  @override
  String get confirmYes => 'Confirmar';

  @override
  String get authEmailHint => 'Correo electrónico';

  @override
  String get authEmailRequired => 'Introduce tu correo electrónico';

  @override
  String get authEmailInvalid => 'Introduce un correo electrónico válido';

  @override
  String get authPasswordHint => 'Contraseña';

  @override
  String get authPasswordRequired => 'Introduce tu contraseña';

  @override
  String get authPasswordMin6 =>
      'La contraseña debe tener al menos 6 caracteres';

  @override
  String get authConfirmPasswordHint => 'Confirmar contraseña';

  @override
  String get authPasswordMismatch => 'Las contraseñas no coinciden';

  @override
  String get authUsernameOptionalHint => 'Nombre de usuario (opcional)';

  @override
  String get authLoginButton => 'Iniciar sesión';

  @override
  String get authRegisterButton => 'Registrarse';

  @override
  String get authNoAccount => '¿No tienes cuenta? Regístrate';

  @override
  String get authHaveAccount => '¿Ya tienes cuenta? Inicia sesión';

  @override
  String get authCreateAccount => 'Crear cuenta';

  @override
  String get authOrLoginWith => 'O inicia sesión con';

  @override
  String get authGoogleLogin => 'Iniciar sesión con Google';

  @override
  String get authAppleLogin => 'Iniciar sesión con Apple';

  @override
  String get authOr => 'O';

  @override
  String get authGuestLogin => 'Continuar como invitado';

  @override
  String get authLoginFailed =>
      'Error al iniciar sesión, comprueba tu correo y contraseña';

  @override
  String get authRegisterFailed =>
      'Error al registrarse, el correo puede estar ya en uso';

  @override
  String get authGoogleCancelled => 'Inicio de sesión con Google cancelado';

  @override
  String get authGoogleFailed =>
      'Error al iniciar sesión con Google, inténtalo de nuevo';

  @override
  String get authGoogleError => 'Error de inicio de sesión con Google';

  @override
  String get authGoogleNotConfigured =>
      'Inicio de sesión con Google no configurado, contacta al administrador';

  @override
  String get authGoogleNetworkError =>
      'Error de red al iniciar sesión con Google, comprueba tu conexión';

  @override
  String get authAppleOnlyApple =>
      'El inicio de sesión con Apple solo es compatible con iOS y macOS';

  @override
  String get authAppleCancelled => 'Inicio de sesión con Apple cancelado';

  @override
  String get authAppleFailed =>
      'Error al iniciar sesión con Apple, inténtalo de nuevo';

  @override
  String get authAppleError => 'Error de inicio de sesión con Apple';

  @override
  String get authAppleNotConfigured =>
      'Inicio de sesión con Apple no configurado';

  @override
  String get authGuestFailed =>
      'Error al iniciar sesión como invitado, inténtalo de nuevo';

  @override
  String get authGuestError => 'Error de inicio de sesión como invitado';

  @override
  String get recCandidatesTitle => '¿Es esta obra?';

  @override
  String get recNoneOfThese => 'Ninguna de estas';

  @override
  String get recNotRecognized => 'No se reconoció esta obra';

  @override
  String recLabelSeen(String text) {
    return 'La etiqueta dice «$text» — aún no tenemos su guía completa, pero hemos anotado tu solicitud ✅';
  }

  @override
  String get recShootLabelBtn => 'Fotografía la cartela';

  @override
  String get recShootLabelHint =>
      'Las cartelas del museo muestran el título y el artista — fotografíala y podremos identificar la obra';

  @override
  String get recViewfinderLabelHint =>
      'Apunta al texto de la cartela, llena el encuadre';

  @override
  String get camNoCamera => 'No se encontró ninguna cámara';

  @override
  String get camInitFailed => 'Error al inicializar la cámara';

  @override
  String get camTagSearch => 'Búsqueda por cartela';

  @override
  String get camTagHint =>
      'En zonas sin foto, introduce el número de cartela, título o artista';

  @override
  String get camTagExample => 'p. ej. INV 3692 / El dormitorio';

  @override
  String get camPackComingSoon =>
      'La búsqueda en la colección se abrirá cuando estén los paquetes sin conexión';

  @override
  String get camQuotaUsedUp => 'Escaneos gratis agotados';

  @override
  String get camUpgradeHint =>
      'Mejora para seguir escuchando por todo el museo';

  @override
  String get camViewUpgrade => 'Ver planes de mejora';

  @override
  String get camCantPhoto =>
      '¿No puedes hacer foto? Introduce el número de cartela';

  @override
  String get camRecognizing => 'Reconociendo…';

  @override
  String get camComparing =>
      'La IA compara con colecciones y bases de datos de arte públicas';

  @override
  String get camConfirmPrompt => 'Reconocimiento completado, confirma la obra';

  @override
  String get camConfidence => 'Confianza';

  @override
  String get camConfirmStart => 'Confirmar e iniciar guía';

  @override
  String get camNoneSearch =>
      '¿Ninguna coincide? Busca por título o número de cartela →';

  @override
  String get camRecognizeFailed => 'Error de reconocimiento';

  @override
  String get camRetake => 'Repetir';
}
