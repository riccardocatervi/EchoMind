"""Regressione: il worker deve poter importare i suoi moduli task all'avvio.

Il worker Celery importa `worker.tasks.echo` per PRIMO (e' il primo della config
`imports`). Se esiste un ciclo di import worker.tasks --> services --> worker.tasks,
il worker crasha all'avvio con ImportError ("partially initialized module"),
anche se l'intera suite resta verde: pytest importa quei moduli in un ordine
diverso (via l'app/le deps) che NON innesca il ciclo.

Per riprodurre fedelmente l'avvio del worker serve un interprete FRESCO (i moduli
gia' in sys.modules maschererebbero il ciclo): lo lanciamo in subprocess,
importando echo PRIMA di transcribe, come fa il worker.
"""

from __future__ import annotations

import subprocess
import sys


def test_worker_imports_task_modules_without_cycle() -> None:
    code = (
        "import echomind.worker.tasks.echo;"
        "import echomind.worker.tasks.transcribe;"
        "import echomind.worker.tasks.extract;"
        "from echomind.worker.celery_app import celery_app;"
        "names = sorted(t for t in celery_app.tasks if t.startswith('echomind'));"
        "assert names == ['echomind.echo', 'echomind.extract', 'echomind.transcribe'], names;"
        "print('WORKER_BOOTSTRAP_OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    assert "WORKER_BOOTSTRAP_OK" in result.stdout
