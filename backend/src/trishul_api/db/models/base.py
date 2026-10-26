from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM base. The SQL scripts in database/ own the schema: never call create_all()."""


class Audited:
    """Marker: inserts, updates and deletes of these models are written to core.audit_log.

    Set by scripts/model_options.toml; the generator adds it to the model classes.
    """

    #: Columns whose values are masked in the audit trail.
    __audit_masked__: frozenset[str] = frozenset()
    #: Columns not worth recording (housekeeping).
    __audit_ignored__: frozenset[str] = frozenset(
        {"id", "created_at", "created_by_user_id", "updated_at", "updated_by_user_id", "row_version"}
    )
