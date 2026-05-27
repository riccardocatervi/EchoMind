#!/usr/bin/env python3
"""Vieta pattern di credenziali REALI nei file di test/workflow CI.

Eseguito da: hook pre-commit (vedi .pre-commit-config.yaml)

Filosofia
=========
I file di test contengono per design segreti dummy con prefisso convenzionale
(`test-`, `ci-dummy-`, `wrong-`). Ma una vera chiave OpenAI/AWS/GitHub/...
non deve MAI finire lì.

Lo script ha DUE check complementari:

A. **Pattern provider-specific**: regex per chiavi di provider noti
   (OpenAI `sk-...`, AWS `AKIA...`, GitHub `ghp_...`, ecc.). Se anche uno
   di questi compare in un file di test/workflow, fail.

B. **Pattern generic-key-without-dummy-prefix**: cerca assegnazioni del tipo
   `*_KEY = "..."`/`*_SECRET = "..."` dove il valore NON inizia con un
   prefisso convenzionale dummy. Cattura il caso "ho copiato una vera chiave
   e l'ho messa in un test senza usare il prefisso giusto".

Convenzione exit code:
  0 = pulito
  1 = sospetto trovato → commit bloccato
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# -----------------------------------------------------------------------------
# Configurazione
# -----------------------------------------------------------------------------
TARGET_DIRS = ["backend/tests", ".github/workflows"]
DUMMY_PREFIXES = ("test-", "ci-dummy-", "wrong-")
EXCLUDE_SUFFIXES = (".pyc", ".cache")

# Pattern A: provider-specific
PROVIDER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI key (sk-...)", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("Anthropic key (sk-ant-...)", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("AWS access key (AKIA...)", re.compile(r"\bAKIA[A-Z0-9]{16}\b")),
    (
        "AWS secret access key (aws_secret_access_key=...)",
        re.compile(
            r"aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}\b",
            re.IGNORECASE,
        ),
    ),
    ("GitHub PAT classic (ghp_...)", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("GitHub PAT fine-grained", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82,}\b")),
    ("Slack token", re.compile(r"\bxox[abp]-[A-Za-z0-9-]{10,}")),
]

# Pattern B: variabili maiuscole *_KEY/_SECRET/_TOKEN con valore "lungo"
# senza prefisso dummy. La regex cattura il valore in un gruppo.
GENERIC_KEY_ASSIGN = re.compile(
    r"""
    \b
    (?P<varname>[A-Z][A-Z0-9_]*_(?:KEY|SECRET|TOKEN))   # NAME_KEY etc.
    \s* [=:] \s*
    (?P<quote>["'])
    (?P<value>[^"'\n]{20,})                            # valore lungo
    (?P=quote)
    """,
    re.VERBOSE,
)


def is_dummy_value(value: str) -> bool:
    """True se il valore inizia con uno dei prefissi convenzionali dummy."""
    return any(value.startswith(p) for p in DUMMY_PREFIXES)


def iter_target_files(root: Path) -> list[Path]:
    """Ritorna tutti i file da scansionare (escludendo build artifacts)."""
    files: list[Path] = []
    for target in TARGET_DIRS:
        base = root / target
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(str(p).endswith(s) for s in EXCLUDE_SUFFIXES):
                continue
            if "__pycache__" in p.parts:
                continue
            # Skip questo stesso script (contiene i pattern di esempio
            # come stringhe regex, che farebbero auto-match se finissimo qui)
            files.append(p)
    return files


def scan_file(path: Path) -> list[str]:
    """Ritorna lista di descrizioni dei finding sospetti nel file (vuota se ok)."""
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings  # skip binari/illeggibili

    # Pattern A
    for description, pattern in PROVIDER_PATTERNS:
        for match in pattern.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            findings.append(
                f"  {path}:{line_no} → {description}: {match.group()[:40]}..."
            )

    # Pattern B: cerca *_KEY = "..." dove il valore NON è dummy
    for match in GENERIC_KEY_ASSIGN.finditer(text):
        value = match.group("value")
        if is_dummy_value(value):
            continue
        # Filtra falsi positivi noti: pattern reference dentro regex string
        # (es. la nostra regex sopra contiene "AKIA[A-Z0-9]{16}")
        if "[" in value or "{" in value:
            continue
        line_no = text[: match.start()].count("\n") + 1
        findings.append(
            f"  {path}:{line_no} → suspect non-dummy {match.group('varname')}: "
            f'"{value[:40]}..."'
        )

    return findings


def main() -> int:
    root = Path(__file__).parent.parent
    files = iter_target_files(root)

    all_findings: list[str] = []
    for f in files:
        # Skip questo stesso script: i pattern qui sono regex template,
        # non vere chiavi.
        if f.name == "check_no_real_secrets_in_tests.py":
            continue
        all_findings.extend(scan_file(f))

    if not all_findings:
        return 0

    print("✗ Suspect REAL credentials in test/workflow files:")
    for f in all_findings:
        print(f)
    print()
    print("These files should contain only DUMMY values. Use a prefix like")
    print("'test-', 'ci-dummy-', or 'wrong-' for hardcoded secrets, OR move")
    print("real values to GitHub Actions repository secrets.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
