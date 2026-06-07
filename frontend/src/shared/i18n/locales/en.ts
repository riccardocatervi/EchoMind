/**
 * English translations.
 */
const en = {
  // ---------------------------------------------------------------------------
  // Landing page
  // ---------------------------------------------------------------------------
  "landing.tagline.before": "Transform your documents into ",
  "landing.tagline.highlight": "knowledge graphs",
  "landing.tagline.after": ".",
  "landing.description":
    "Upload texts, PDFs or audio. EchoMind transcribes them, extracts key entities and builds a visual map of connections.",
  "landing.login": "Sign in",
  "landing.signup": "Sign up",
  "landing.phrases": JSON.stringify([
    "Transform documents into knowledge graphs.",
    "Discover connections between key concepts.",
    "From audio to graph, in minutes.",
    "Every text hides a structure.",
    "Extract, connect, understand.",
  ]),

  // ---------------------------------------------------------------------------
  // Auth — login
  // ---------------------------------------------------------------------------
  "auth.login.title": "EchoMind",
  "auth.login.description": "Sign in to your workspace",
  "auth.login.submit": "Sign in",
  "auth.login.noAccount": "Don't have an account?",
  "auth.login.signupLink": "Sign up",
  "auth.login.forgot": "Forgot password?",

  // Auth — signup
  "auth.signup.title": "EchoMind",
  "auth.signup.description": "Create your account",
  "auth.signup.firstName": "First name",
  "auth.signup.lastName": "Last name",
  "auth.signup.submit": "Sign up",
  "auth.signup.hasAccount": "Already have an account?",
  "auth.signup.loginLink": "Sign in",
  "auth.signup.confirmEmail": "Registration received. Check your email to confirm your account.",

  // Auth — forgot password
  "auth.forgot.title": "Forgot password",
  "auth.forgot.description": "Enter your email to receive a reset link",
  "auth.forgot.submit": "Send link",
  "auth.forgot.success": "Email sent! Check your inbox and click the link to set a new password.",
  "auth.forgot.backToLogin": "Back to login",

  // Auth — reset password
  "auth.reset.title": "New password",
  "auth.reset.description": "Choose a new password for your account",
  "auth.reset.newPassword": "New password",
  "auth.reset.confirmPassword": "Confirm password",
  "auth.reset.submit": "Update password",
  "auth.reset.success": "Password updated! You can now sign in with your new credentials.",
  "auth.reset.checking": "Verifying link...",
  "auth.reset.expired":
    "The link has expired or is invalid. Request a new link from the login page.",
  "auth.reset.mismatch": "Passwords do not match.",
  "auth.reset.minLength": "Password must be at least 6 characters.",

  "auth.field.email": "Email",
  "auth.field.password": "Password",

  // ---------------------------------------------------------------------------
  // App shell / navigation
  // ---------------------------------------------------------------------------
  "app.logout": "Sign out",
  "app.profile": "Profile",

  // ---------------------------------------------------------------------------
  // Profile
  // ---------------------------------------------------------------------------
  "profile.title": "Profile",
  "profile.back": "Documents",
  // Personalised greeting: {{name}} is replaced with first name or email
  "profile.greeting": "Hi, {{name}}. Want to change something?",
  "profile.name.title": "Edit name",
  "profile.name.firstName": "First name",
  "profile.name.lastName": "Last name",
  "profile.name.submit": "Save name",
  "profile.name.success": "Name updated successfully.",
  "profile.email.title": "Change email",
  "profile.email.current": "Current email",
  "profile.email.new": "New email",
  "profile.email.submit": "Update email",
  "profile.email.success": "Confirmation email sent to the new address. Check your inbox.",
  "profile.password.title": "Change password",
  "profile.password.new": "New password",
  "profile.password.confirm": "Confirm password",
  "profile.password.submit": "Update password",
  "profile.password.success": "Password updated successfully.",
  "profile.password.mismatch": "Passwords do not match.",
  "profile.delete.title": "Delete account",
  "profile.delete.warning":
    "All your documents, transcripts, summaries and knowledge graphs will be permanently deleted along with your account. This action is irreversible.",
  "profile.delete.trigger": "Delete account",
  "profile.delete.dialog.title": "Delete your account?",
  "profile.delete.dialog.description":
    "You are about to permanently delete your EchoMind account and all associated data: documents, transcripts, summaries and knowledge graphs. You will not be able to recover anything.",
  "profile.delete.dialog.cancel": "Cancel",
  "profile.delete.dialog.confirm": "Delete permanently",
  "profile.delete.success": "Account deleted",
  "profile.delete.error": "Unable to delete account. Please try again later.",

  // ---------------------------------------------------------------------------
  // Documents — dashboard
  // ---------------------------------------------------------------------------
  "docs.title": "Your documents",
  "docs.subtitle": "Upload texts or audio and turn them into knowledge graphs.",
  "docs.upload": "Upload document",
  "docs.empty.title": "No documents yet",
  "docs.empty.subtitle": 'Use "Upload document" to get started.',
  "docs.error": "Unable to load documents",
  "docs.searchPlaceholder": "Search by filename...",
  "docs.searchEmpty": 'No documents found for "{{query}}".',

  // ---------------------------------------------------------------------------
  // Upload dialog
  // ---------------------------------------------------------------------------
  "upload.dialog.title": "Upload a document",
  "upload.dialog.description":
    "Text (PDF, DOCX, TXT) or audio (MP3, WAV, M4A). Transcription and graph extraction start automatically after upload.",
  "upload.progress": "Uploading... {{percent}}%",
  "upload.checking": "Verifying file...",
  "upload.cancel": "Cancel",
  "upload.submit": "Upload",
  "upload.success": "Document uploaded. Processing started.",
  "upload.error.mimeType": "File content does not match the declared type.",
  "upload.error.failed": "Upload failed.",

  // ---------------------------------------------------------------------------
  // Dropzone
  // ---------------------------------------------------------------------------
  "dropzone.unsupportedType": "Unsupported file type (PDF, DOCX, TXT, MP3, WAV, M4A).",
  "dropzone.tooLarge": "File too large (max {{max}}).",
  "dropzone.removeFile": "Remove file",
  "dropzone.hint": "Drag a file here or click to choose",
  "dropzone.formats": "PDF, DOCX, TXT, MP3, WAV, M4A · max {{max}}",

  // ---------------------------------------------------------------------------
  // Graph (full-canvas page)
  // ---------------------------------------------------------------------------
  "graph.back": "Document",
  "graph.loading": "Loading graph...",
  "graph.notReady": "The graph is not ready yet.",
  "graph.backendUnavailable": "The graph backend (Neo4j) is unavailable.",
  "graph.loadError": "Error loading the graph.",
  "graph.empty": "No nodes in the graph.",

  // ---------------------------------------------------------------------------
  // Documents — detail
  // ---------------------------------------------------------------------------
  "doc.back": "Documents",
  "doc.exploreGraph": "Explore graph",
  "doc.reExtract": "Re-extract graph",
  "doc.reExtracting": "Re-extracting...",
  "doc.status.uploading": "Transcription in progress...",
  "doc.status.transcribed": "Extracting knowledge graph...",
  "doc.status.extracted": "Generating summary...",
  "doc.status.stuck":
    'Processing seems stuck. The worker may have exhausted its retries (e.g. API limit). Use "Re-extract graph" to retry.',

  // ---------------------------------------------------------------------------
  // Status badge
  // ---------------------------------------------------------------------------
  "status.pending": "Loading",
  "status.uploaded": "Processing",
  "status.transcribed": "Transcribed",
  "status.extracted": "Extracted",
  "status.completed": "Completed",
  "status.failed": "Failed",

  // ---------------------------------------------------------------------------
  // Pipeline steps
  // ---------------------------------------------------------------------------
  "pipeline.uploaded": "Uploaded",
  "pipeline.transcribed": "Transcribed",
  "pipeline.extracted": "Extracted",
  "pipeline.completed": "Completed",

  // ---------------------------------------------------------------------------
  // Delete dialog
  // ---------------------------------------------------------------------------
  "doc.delete.title": "Delete document?",
  "doc.delete.description":
    '"{{filename}}" will be permanently removed, along with its transcript, summary and graph. This action is irreversible.',
  "doc.delete.trigger": "Delete document",
  "doc.delete.cancel": "Cancel",
  "doc.delete.confirm": "Delete",
  "doc.delete.success": "Document deleted",
  "doc.delete.error": "Deletion failed",

  // ---------------------------------------------------------------------------
  // Re-extraction toasts
  // ---------------------------------------------------------------------------
  "doc.extractionComplete": "Extraction complete",
  "doc.extractionFailed": "Extraction failed",
  "doc.reExtractionStarted": "Re-extraction started",
  "doc.reExtractionError": "Failed to start extraction",
  "doc.status.failureDefault": "File upload or validation failed.",

  // ---------------------------------------------------------------------------
  // Common
  // ---------------------------------------------------------------------------
  "common.open": "Open",
  "common.nodes": "nodes",
} as const;

export default en;
