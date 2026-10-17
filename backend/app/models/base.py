import enum

from sqlalchemy import Enum, MetaData
from sqlalchemy.orm import DeclarativeBase

# Explicit naming convention so Alembic autogenerate produces stable,
# predictable constraint/index names instead of dialect-dependent defaults.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Postgres enum persisted by value ("pending") rather than member name ("PENDING")."""
    return Enum(enum_cls, name=name, values_callable=lambda members: [member.value for member in members])
