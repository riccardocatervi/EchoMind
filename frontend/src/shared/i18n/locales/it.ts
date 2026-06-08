/**
 * Traduzioni italiane (lingua di default).
 * Struttura piatta con prefisso per namespace: "landing.", "auth.", "app.", ecc.
 */
const it = {
  // ---------------------------------------------------------------------------
  // Landing page
  // ---------------------------------------------------------------------------
  "landing.tagline.before": "Trasforma i tuoi documenti in ",
  "landing.tagline.highlight": "grafi di conoscenza",
  "landing.tagline.after": ".",
  "landing.description":
    "Carica testi, PDF o audio. EchoMind li trascrive, estrae le entità chiave e costruisce una mappa visiva delle connessioni.",
  "landing.login": "Accedi",
  "landing.signup": "Registrati",
  "landing.phrases": JSON.stringify([
    "Trasforma i documenti in grafi di conoscenza.",
    "Scopri le connessioni tra i concetti chiave.",
    "Dall'audio al grafo, in pochi minuti.",
    "Ogni testo nasconde una struttura.",
    "Estrai, connetti, comprendi.",
  ]),

  // ---------------------------------------------------------------------------
  // Auth — login
  // ---------------------------------------------------------------------------
  "auth.login.title": "EchoMind",
  "auth.login.description": "Accedi al tuo spazio",
  "auth.login.submit": "Accedi",
  "auth.login.noAccount": "Non hai un account?",
  "auth.login.signupLink": "Registrati",
  "auth.login.forgot": "Password dimenticata?",

  // Auth — signup
  "auth.signup.title": "EchoMind",
  "auth.signup.description": "Crea il tuo account",
  "auth.signup.firstName": "Nome",
  "auth.signup.lastName": "Cognome",
  "auth.signup.submit": "Registrati",
  "auth.signup.hasAccount": "Hai già un account?",
  "auth.signup.loginLink": "Accedi",
  "auth.signup.confirmEmail":
    "Registrazione ricevuta. Controlla la tua email per confermare l'account.",

  // Auth — forgot password
  "auth.forgot.title": "Password dimenticata",
  "auth.forgot.description": "Inserisci la tua email per ricevere il link di reset",
  "auth.forgot.submit": "Invia link",
  "auth.forgot.success":
    "Email inviata! Controlla la tua casella di posta e clicca il link per impostare una nuova password.",
  "auth.forgot.backToLogin": "Torna al login",

  // Auth — reset password
  "auth.reset.title": "Nuova password",
  "auth.reset.description": "Scegli una nuova password per il tuo account",
  "auth.reset.newPassword": "Nuova password",
  "auth.reset.confirmPassword": "Conferma password",
  "auth.reset.submit": "Aggiorna password",
  "auth.reset.success": "Password aggiornata! Puoi ora accedere con le nuove credenziali.",
  "auth.reset.checking": "Verifica del link in corso...",
  "auth.reset.expired":
    "Il link è scaduto o non valido. Richiedi un nuovo link dalla pagina di login.",
  "auth.reset.mismatch": "Le password non corrispondono.",
  "auth.reset.minLength": "La password deve contenere almeno 6 caratteri.",

  "auth.field.email": "Email",
  "auth.field.password": "Password",
  "auth.password.show": "Mostra password",
  "auth.password.hide": "Nascondi password",

  // ---------------------------------------------------------------------------
  // App shell / navigazione
  // ---------------------------------------------------------------------------
  "app.logout": "Esci",
  "app.profile": "Profilo",

  // ---------------------------------------------------------------------------
  // Profilo
  // ---------------------------------------------------------------------------
  "profile.title": "Profilo",
  "profile.back": "Documenti",
  // Saluto personalizzato: {{name}} e' sostituito con nome o email
  "profile.greeting": "Ciao, {{name}}. Vuoi cambiare qualcosa?",
  "profile.name.title": "Modifica nome",
  "profile.name.firstName": "Nome",
  "profile.name.lastName": "Cognome",
  "profile.name.submit": "Salva nome",
  "profile.name.success": "Nome aggiornato con successo.",
  "profile.email.title": "Cambia email",
  "profile.email.current": "Email corrente",
  "profile.email.new": "Nuova email",
  "profile.email.submit": "Aggiorna email",
  "profile.email.success":
    "Email di conferma inviata al nuovo indirizzo. Controlla la tua casella.",
  "profile.password.title": "Cambia password",
  "profile.password.new": "Nuova password",
  "profile.password.confirm": "Conferma password",
  "profile.password.submit": "Aggiorna password",
  "profile.password.success": "Password aggiornata con successo.",
  "profile.password.mismatch": "Le password non corrispondono.",
  "profile.language.title": "Lingua di output",
  "profile.language.subtitle":
    "Lingua usata per riassunti, grafi di conoscenza e risposte alle domande.",
  "profile.language.it": "Italiano",
  "profile.language.en": "Inglese",
  "profile.language.success": "Lingua di output aggiornata.",
  "profile.language.error": "Impossibile aggiornare la lingua. Riprova.",

  "profile.delete.title": "Elimina account",
  "profile.delete.warning":
    "Tutti i tuoi documenti, trascrizioni, riassunti e grafi di conoscenza verranno eliminati definitivamente insieme all'account. Questa operazione è irreversibile.",
  "profile.delete.trigger": "Elimina account",
  "profile.delete.dialog.title": "Eliminare l'account?",
  "profile.delete.dialog.description":
    "Stai per eliminare definitivamente il tuo account EchoMind e tutti i dati associati: documenti, trascrizioni, riassunti e grafi di conoscenza. Non potrai recuperare nulla.",
  "profile.delete.dialog.cancel": "Annulla",
  "profile.delete.dialog.confirm": "Elimina definitivamente",
  "profile.delete.success": "Account eliminato",
  "profile.delete.error": "Impossibile eliminare l'account. Riprova più tardi.",

  // ---------------------------------------------------------------------------
  // Documenti — dashboard
  // ---------------------------------------------------------------------------
  "docs.title": "I tuoi documenti",
  "docs.subtitle": "Butta dentro testi o audio e lasciaci sbrogliare la matassa.",
  "docs.languageHint":
    "Personalizza la lingua di riassunti e grafi nelle <link>impostazioni del profilo</link>.",
  "docs.upload": "Carica documento",
  "docs.empty.title": "Ancora nessun documento. Cosa stai aspettando?",
  "docs.empty.subtitle": 'Usa "Carica documento" per dare inizio alle danze.',
  "docs.error": "Impossibile caricare i documenti",
  "docs.searchPlaceholder": "Cerca per nome file...",
  "docs.searchEmpty": 'Sei sicuro che si chiami proprio "{{query}}"? Non abbiamo trovato nulla!',

  // ---------------------------------------------------------------------------
  // Upload dialog
  // ---------------------------------------------------------------------------
  "upload.dialog.title": "Carica un documento",
  "upload.dialog.description":
    "Testo (PDF, DOCX, TXT) o audio (MP3, WAV, M4A). Dopo il caricamento partono automaticamente trascrizione ed estrazione del grafo.",
  "upload.progress": "Caricamento... {{percent}}%",
  "upload.checking": "Verifica del file in corso...",
  "upload.cancel": "Annulla",
  "upload.submit": "Carica",
  "upload.success": "Documento caricato. Elaborazione avviata.",
  "upload.error.mimeType": "Il contenuto del file non corrisponde al tipo dichiarato.",
  "upload.error.failed": "Upload fallito.",

  // ---------------------------------------------------------------------------
  // Dropzone
  // ---------------------------------------------------------------------------
  "dropzone.unsupportedType": "Tipo di file non supportato (PDF, DOCX, TXT, MP3, WAV, M4A).",
  "dropzone.tooLarge": "File troppo grande (max {{max}}).",
  "dropzone.removeFile": "Rimuovi file",
  "dropzone.hint": "Trascina un file o clicca per sceglierlo",
  "dropzone.formats": "PDF, DOCX, TXT, MP3, WAV, M4A · max {{max}}",

  // ---------------------------------------------------------------------------
  // Grafo (pagina full-canvas)
  // ---------------------------------------------------------------------------
  "graph.back": "Documento",
  "graph.loading": "Caricamento grafo...",
  "graph.notReady": "Il grafo non è ancora pronto.",
  "graph.backendUnavailable": "Il backend del grafo (Neo4j) non è raggiungibile.",
  "graph.loadError": "Errore nel caricamento del grafo.",
  "graph.empty": "Nessun nodo nel grafo.",
  "graph.qa.title": "Chiedi al grafo",
  "graph.qa.placeholder": "Fai una domanda sul documento...",
  "graph.qa.send": "Invia",
  "graph.qa.asking": "Sto pensando...",
  "graph.qa.sources": "Fonti",
  "graph.qa.hint": "Le risposte si basano solo sul grafo di questo documento.",
  "graph.qa.notReady": "Il documento non è ancora pronto per le domande.",
  "graph.qa.unavailable": "Il servizio di Q&A (Gemini) non è al momento disponibile.",
  "graph.qa.error": "Errore durante la generazione della risposta.",
  "graph.controls.searchPlaceholder": "Cerca nodo...",
  "graph.controls.searchLabel": "Cerca nodo",
  "graph.controls.clearSearch": "Pulisci ricerca",
  "graph.controls.communities": "Community",
  "graph.controls.community": "Community {{n}}",
  "graph.details.close": "Chiudi pannello",
  "graph.details.relations": "Relazioni ({{n}})",
  "graph.details.goTo": "Vai a {{name}}",
  "summary.title": "Riassunto",
  "summary.stats.nodes": "{{n}} nodi",
  "summary.stats.relationships": "{{n}} relazioni",
  "summary.stats.communities": "{{n}} community",

  // ---------------------------------------------------------------------------
  // Documenti — dettaglio
  // ---------------------------------------------------------------------------
  "doc.transcript": "Trascrizione",
  "doc.transcript.chars": "caratteri",
  "doc.transcript.lang": "lingua",
  "doc.back": "Documenti",
  "doc.exploreGraph": "Esplora il grafo",
  "doc.reExtract": "Ri-estrai grafo",
  "doc.reExtracting": "Ri-estrazione in corso...",
  "doc.status.uploading": "Trascrizione in corso...",
  "doc.status.transcribed": "Estrazione del grafo di conoscenza in corso...",
  "doc.status.extracted": "Generazione del riassunto in corso...",
  "doc.status.stuck":
    'L\'elaborazione sembra bloccata. Il worker potrebbe aver esaurito i tentativi (es. limite API). Usa "Ri-estrai grafo" per riprovare.',

  // ---------------------------------------------------------------------------
  // Status badge
  // ---------------------------------------------------------------------------
  "status.pending": "In caricamento",
  "status.uploaded": "In elaborazione",
  "status.transcribed": "Trascritto",
  "status.extracted": "Estratto",
  "status.completed": "Completato",
  "status.failed": "Fallito",

  // ---------------------------------------------------------------------------
  // Pipeline steps
  // ---------------------------------------------------------------------------
  "pipeline.uploaded": "Caricato",
  "pipeline.transcribed": "Trascritto",
  "pipeline.extracted": "Estratto",
  "pipeline.completed": "Completato",

  // ---------------------------------------------------------------------------
  // Delete dialog
  // ---------------------------------------------------------------------------
  "doc.delete.title": "Eliminare il documento?",
  "doc.delete.description":
    '"{{filename}}" verrà rimosso definitivamente, insieme a transcript, riassunto e grafo. L\'operazione è irreversibile.',
  "doc.delete.trigger": "Elimina documento",
  "doc.delete.cancel": "Annulla",
  "doc.delete.confirm": "Elimina",
  "doc.delete.success": "Documento eliminato",
  "doc.delete.error": "Eliminazione fallita",

  // ---------------------------------------------------------------------------
  // Re-extraction toasts
  // ---------------------------------------------------------------------------
  "doc.extractionComplete": "Estrazione completata",
  "doc.extractionFailed": "Estrazione fallita",
  "doc.reExtractionStarted": "Ri-estrazione avviata",
  "doc.reExtractionError": "Avvio estrazione fallito",
  "doc.status.failureDefault": "Caricamento o validazione del file fallita.",

  // ---------------------------------------------------------------------------
  // Common
  // ---------------------------------------------------------------------------
  "common.open": "Apri",
  "common.nodes": "nodi",
} as const;

export default it;
