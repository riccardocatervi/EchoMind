#!/usr/bin/env bash
# =============================================================================
# EchoMind — verifica prerequisiti host
#
# Eseguito da: `make check-env`
# Scopo: dare un report chiaro all'utente PRIMA che provi `make install` o
# `make dev` e si trovi davanti errori criptici (es. "command not found: uv").
#
# Convenzione exit code:
#   0 = tutto ok
#   1 = almeno un requisito mancante
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
    GREEN='\033[32m'
    RED='\033[31m'
    YELLOW='\033[33m'
    BLUE='\033[34m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    GREEN='' RED='' YELLOW='' BLUE='' BOLD='' RESET=''
fi

ok()    { printf "  ${GREEN}✓${RESET} %s\n" "$1"; }
fail()  { printf "  ${RED}✗${RESET} %s\n" "$1"; FAILED=1; }
warn()  { printf "  ${YELLOW}!${RESET} %s\n" "$1"; }
info()  { printf "${BLUE}${BOLD}%s${RESET}\n" "$1"; }

FAILED=0

# ---------------------------------------------------------------------------
# Helper: confronto versione semver-like (X.Y.Z >= REQUIRED)
# Ritorna 0 se ACTUAL >= REQUIRED, 1 altrimenti.
# ---------------------------------------------------------------------------
version_ge() {
    # $1 = actual, $2 = required
    [[ "$(printf '%s\n' "$2" "$1" | sort -V | head -n1)" == "$2" ]]
}

# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------
info "EchoMind — controllo prerequisiti host"
echo

# --- Python 3.12+ ---
if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
    if version_ge "$PY_VER" "3.12.0"; then
        ok "Python $PY_VER (≥ 3.12)"
    else
        fail "Python $PY_VER trovato, ma serve ≥ 3.12. Installa Python 3.12+: https://www.python.org/downloads/"
    fi
else
    fail "python3 non trovato. Installa Python ≥ 3.12: https://www.python.org/downloads/"
fi

# --- uv ---
if command -v uv >/dev/null 2>&1; then
    UV_VER=$(uv --version 2>&1 | awk '{print $2}')
    ok "uv $UV_VER"
else
    fail "uv non trovato. Installazione: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# --- Docker ---
if command -v docker >/dev/null 2>&1; then
    DOCKER_VER=$(docker --version 2>&1 | awk -F'[ ,]' '{print $3}')
    ok "docker $DOCKER_VER"

    # Docker daemon in esecuzione?
    if docker info >/dev/null 2>&1; then
        ok "docker daemon attivo"
    else
        fail "docker installato ma il daemon non risponde. Avvia Docker Desktop."
    fi
else
    fail "docker non trovato. Installa Docker Desktop: https://www.docker.com/products/docker-desktop/"
fi

# --- Docker Compose v2 (plugin, non `docker-compose` legacy) ---
if docker compose version >/dev/null 2>&1; then
    COMPOSE_VER=$(docker compose version --short 2>&1)
    ok "docker compose v$COMPOSE_VER (plugin)"
else
    fail "docker compose v2 non disponibile. Aggiorna Docker Desktop alla versione recente."
fi

# --- Git ---
if command -v git >/dev/null 2>&1; then
    GIT_VER=$(git --version 2>&1 | awk '{print $3}')
    ok "git $GIT_VER"
else
    warn "git non trovato (necessario per pre-commit, ma non per dev infra)"
fi

# --- Make ---
if command -v make >/dev/null 2>&1; then
    ok "GNU make disponibile"
else
    fail "make non trovato. Su macOS: 'xcode-select --install'. Su Linux: 'apt install make'."
fi

# --- .env presente? ---
echo
info "Configurazione locale"
if [[ -f .env ]]; then
    ok ".env presente"
else
    warn ".env non presente. Verrà creato da .env.example al primo 'make infra-up'."
fi

# ---------------------------------------------------------------------------
# Esito
# ---------------------------------------------------------------------------
echo
if [[ $FAILED -eq 0 ]]; then
    info "✓ Tutti i prerequisiti soddisfatti."
    exit 0
else
    info "✗ Risolvi i problemi sopra elencati e riprova."
    exit 1
fi
