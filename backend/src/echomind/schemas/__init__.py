"""Pydantic schemas: I/O della API HTTP.

Convenzione:
- I "modelli" SQLAlchemy vivono in `db/models/`
- Gli "schemas" Pydantic vivono qui

Separazione netta: i modelli ORM non escono mai dall'API.
Tutto ciò che attraversa il confine HTTP è uno schema Pydantic.
"""
