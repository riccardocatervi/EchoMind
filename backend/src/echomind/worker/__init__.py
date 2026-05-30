"""Worker layer: Celery app, runtime DB del worker e task asincroni.

È un processo SEPARATO dall'API (entrypoint: `make worker`). Condivide model,
repository e service con l'API, ma ha il proprio engine DB (vedi runtime.py)
perché gira in un altro processo e non può riusare l'engine dell'app FastAPI.
"""
