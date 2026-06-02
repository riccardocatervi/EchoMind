"""Celery application: broker RabbitMQ + result backend Redis + code con DLQ.

Entrypoint CLI del worker:
    celery -A echomind.worker.celery_app:celery_app worker -l info -Q echomind.default

Topologia delle code (vedi ADR-0005):
- `echomind.default`: coda di lavoro. Dichiarata con `x-dead-letter-exchange`,
  così i messaggi REJECTED (basic.reject/nack con requeue=false), scaduti o in
  overflow vengono ripubblicati sulla dead-letter exchange.
- `echomind.dead`: dead-letter queue. Vi atterrano i task che hanno esaurito i
  retry -- l'echo task, sul fallimento terminale, fa `raise Reject(requeue=False)`.
  Ispezionabile dalla management UI di RabbitMQ.

Config di affidabilità:
- task_acks_late=True: il messaggio è ack-ato DOPO il completamento, non alla
  presa. Se il worker muore a metà, RabbitMQ riconsegna (at-least-once delivery).
- task_reject_on_worker_lost=True: worker ucciso --> reject --> dead-letter.
- worker_prefetch_multiplier=1: un messaggio alla volta per worker (fairness).
- serializzazione SOLO json: mai pickle (un payload pickle nella coda = RCE).
"""

from __future__ import annotations

from celery import Celery
from celery.signals import worker_ready
from kombu import Exchange, Queue

from echomind.core.config import Settings, get_settings

# Nomi di exchange/coda centralizzati (riusati da task, test e smoke test).
WORK_EXCHANGE = "echomind"
WORK_QUEUE = "echomind.default"
WORK_ROUTING_KEY = "echomind.default"
DEAD_LETTER_EXCHANGE = "echomind.dlx"
DEAD_LETTER_QUEUE = "echomind.dead"
DEAD_LETTER_ROUTING_KEY = "echomind.dead"


def _build_queues() -> tuple[Queue, ...]:
    """Definisce coda di lavoro (con DLX) + dead-letter queue.

    `queue_arguments` viene passato a RabbitMQ alla dichiarazione della coda.
    ATTENZIONE: se la coda esiste già con argomenti diversi, RabbitMQ rifiuta la
    ridichiarazione (PRECONDITION_FAILED 406). Cambiare questi argomenti richiede
    di eliminare prima la coda vecchia (vedi README --> troubleshooting worker).
    """
    work_exchange = Exchange(WORK_EXCHANGE, type="direct")
    dlx = Exchange(DEAD_LETTER_EXCHANGE, type="direct")
    return (
        Queue(
            WORK_QUEUE,
            exchange=work_exchange,
            routing_key=WORK_ROUTING_KEY,
            queue_arguments={
                "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
                "x-dead-letter-routing-key": DEAD_LETTER_ROUTING_KEY,
            },
        ),
        Queue(
            DEAD_LETTER_QUEUE,
            exchange=dlx,
            routing_key=DEAD_LETTER_ROUTING_KEY,
        ),
    )


def make_celery(settings: Settings) -> Celery:
    """Costruisce e configura l'istanza Celery a partire dai Settings."""
    app = Celery("echomind")
    app.conf.update(
        broker_url=settings.rabbitmq_url,
        result_backend=settings.redis_url,
        # --- serializzazione (sicurezza) ---
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        # --- affidabilità / delivery ---
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        # --- routing / code ---
        task_queues=_build_queues(),
        task_default_queue=WORK_QUEUE,
        task_default_exchange=WORK_EXCHANGE,
        task_default_exchange_type="direct",
        task_default_routing_key=WORK_ROUTING_KEY,
        # --- time limits ---
        task_soft_time_limit=settings.task_soft_time_limit_seconds,
        task_time_limit=settings.task_soft_time_limit_seconds + 30,
        # --- result backend ---
        result_expires=24 * 60 * 60,  # TTL 24h sui result in Redis
        # --- tempo ---
        timezone="UTC",
        enable_utc=True,
        # Silenzia il deprecation warning di Celery 6 e ritenta la connessione
        # al broker all'avvio (utile se RabbitMQ parte poco dopo il worker).
        broker_connection_retry_on_startup=True,
        # --- override per debug manuale (NON usato dai test) ---
        task_always_eager=settings.celery_task_always_eager,
        task_eager_propagates=True,
        # --- registrazione dei moduli task ---
        imports=(
            "echomind.worker.tasks.echo",
            "echomind.worker.tasks.transcribe",
            "echomind.worker.tasks.extract",
        ),
    )
    return app


# Istanza module-level: usata dal CLI del worker e importata dall'API per
# l'enqueue. Costruita con i Settings reali (get_settings() è cachato).
celery_app = make_celery(get_settings())


@worker_ready.connect  # type: ignore[untyped-decorator]
def _ensure_dead_letter_topology(**_kwargs: object) -> None:
    """Dichiara DLX exchange + dead-letter queue + binding all'avvio del worker.

    Celery dichiara solo le code che CONSUMA (es. -Q echomind.default). La coda
    echomind.dead non è consumata da nessuno: senza questa dichiarazione
    esplicita l'exchange echomind.dlx non esisterebbe e i messaggi dead-letterati
    da echomind.default verrebbero SCARTATI invece di finire in echomind.dead.
    Dichiarare la Queue crea exchange + coda + binding in un colpo solo.
    """
    dlx = Exchange(DEAD_LETTER_EXCHANGE, type="direct")
    dead_queue = Queue(DEAD_LETTER_QUEUE, exchange=dlx, routing_key=DEAD_LETTER_ROUTING_KEY)
    with celery_app.connection_for_write() as conn:
        dead_queue.bind(conn.default_channel).declare()
