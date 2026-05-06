import csv
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings


class SchemaMetadataError(RuntimeError):
    pass


@dataclass(frozen=True)
class ColumnMetadata:
    column_name: str
    data_type: str
    postgres_type: str
    is_nullable: bool
    is_primary_key: bool
    is_in_unique_constraint: bool
    ordinal_position: int
    default: str | None = None
    max_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None
    datetime_precision: int | None = None
    enum_values: tuple[str, ...] = ()
    foreign_key_membership: tuple[dict, ...] = ()
    unique_constraint_membership: tuple[str, ...] = ()

    @property
    def is_textual(self) -> bool:
        return self.data_type in {
            "character varying",
            "character",
            "text",
            "citext",
        }


@dataclass(frozen=True)
class ForeignKeyMetadata:
    constraint_name: str
    columns: tuple[str, ...]
    reference_schema: str
    reference_table: str
    reference_columns: tuple[str, ...]


@dataclass(frozen=True)
class UniqueConstraintMetadata:
    constraint_name: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class TableMetadata:
    schema: str
    name: str
    relation_kind: str
    primary_key_columns: tuple[str, ...]
    unique_constraints: tuple[UniqueConstraintMetadata, ...]
    foreign_keys: tuple[ForeignKeyMetadata, ...]
    columns: tuple[ColumnMetadata, ...]

    @property
    def key(self) -> str:
        return self.name

    @property
    def column_count(self) -> int:
        return len(self.columns)

    @property
    def has_primary_key(self) -> bool:
        return bool(self.primary_key_columns)

    @property
    def has_foreign_keys(self) -> bool:
        return bool(self.foreign_keys)

    @property
    def columns_by_name(self) -> dict[str, ColumnMetadata]:
        return {column.column_name: column for column in self.columns}

    @property
    def ordered_column_names(self) -> list[str]:
        return [column.column_name for column in self.columns]

    @property
    def searchable_columns(self) -> list[str]:
        names = list(self.primary_key_columns)
        for column in self.columns:
            if column.is_textual and column.column_name not in names:
                names.append(column.column_name)
            if len(names) >= 12:
                break
        if names:
            return names
        return self.ordered_column_names[:8]

    @property
    def default_visible_columns(self) -> list[str]:
        names = list(self.primary_key_columns)
        for column in self.columns:
            if column.column_name not in names:
                names.append(column.column_name)
            if len(names) >= 8:
                break
        return names or self.ordered_column_names[:8]

    @property
    def default_ordering(self) -> str:
        if self.primary_key_columns:
            return self.primary_key_columns[0]
        if self.columns:
            return self.columns[0].column_name
        return ""

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def short_primary_key(self) -> str:
        if not self.primary_key_columns:
            return "None"
        return ", ".join(self.primary_key_columns)


def discover_schema_metadata_path() -> Path:
    configured = getattr(settings, "SCHEMA_METADATA_PATH", "")
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return path
        raise SchemaMetadataError(f"Schema metadata file was not found: {path}")

    search_roots = [settings.BASE_DIR, settings.BASE_DIR.parent]
    patterns = [
        "_WITH_pk_columns*.csv",
        "*WITH_pk_columns*.csv",
    ]
    candidates = []
    for root in search_roots:
        for pattern in patterns:
            candidates.extend(root.glob(pattern))

    if not candidates:
        raise SchemaMetadataError(
            "Schema metadata CSV not found. Set SCHEMA_METADATA_PATH in your environment."
        )

    return max(candidates, key=lambda candidate: candidate.stat().st_mtime)


def _infer_relation_kind(table_name: str) -> str:
    return "view" if table_name.endswith("_view") else "table"


def _parse_columns(raw_fields: str) -> tuple[ColumnMetadata, ...]:
    raw_columns = json.loads(raw_fields)
    columns = []
    for raw_column in raw_columns:
        columns.append(
            ColumnMetadata(
                column_name=raw_column["column_name"],
                data_type=raw_column["data_type"],
                postgres_type=raw_column["postgres_type"],
                is_nullable=raw_column["is_nullable"],
                is_primary_key=raw_column["is_primary_key"],
                is_in_unique_constraint=raw_column["is_in_unique_constraint"],
                ordinal_position=raw_column["ordinal_position"],
                default=raw_column["default"],
                max_length=raw_column["max_length"],
                numeric_precision=raw_column["numeric_precision"],
                numeric_scale=raw_column["numeric_scale"],
                datetime_precision=raw_column["datetime_precision"],
                enum_values=tuple(raw_column.get("enum_values") or ()),
                foreign_key_membership=tuple(raw_column.get("foreign_key_membership") or ()),
                unique_constraint_membership=tuple(raw_column.get("unique_constraint_membership") or ()),
            )
        )
    return tuple(sorted(columns, key=lambda column: column.ordinal_position))


def _parse_foreign_keys(raw_foreign_keys: str) -> tuple[ForeignKeyMetadata, ...]:
    entries = []
    for raw_fk in json.loads(raw_foreign_keys):
        reference = raw_fk.get("references") or {}
        entries.append(
            ForeignKeyMetadata(
                constraint_name=raw_fk["constraint_name"],
                columns=tuple(raw_fk.get("columns") or ()),
                reference_schema=reference.get("schema", "public"),
                reference_table=reference.get("table", ""),
                reference_columns=tuple(reference.get("columns") or ()),
            )
        )
    return tuple(entries)


def _parse_unique_constraints(raw_unique_constraints: str) -> tuple[UniqueConstraintMetadata, ...]:
    entries = []
    for raw_unique in json.loads(raw_unique_constraints):
        entries.append(
            UniqueConstraintMetadata(
                constraint_name=raw_unique["constraint_name"],
                columns=tuple(raw_unique.get("columns") or ()),
            )
        )
    return tuple(entries)


@lru_cache(maxsize=8)
def load_schema_catalog(metadata_path: str | None = None) -> tuple[TableMetadata, ...]:
    path = Path(metadata_path) if metadata_path else discover_schema_metadata_path()

    with path.open(newline="") as schema_file:
        rows = csv.DictReader(schema_file)
        tables = []
        for row in rows:
            tables.append(
                TableMetadata(
                    schema=row["table_schema"],
                    name=row["table_name"],
                    relation_kind=_infer_relation_kind(row["table_name"]),
                    primary_key_columns=tuple(json.loads(row["primary_key_columns"])),
                    unique_constraints=_parse_unique_constraints(row["unique_constraints"]),
                    foreign_keys=_parse_foreign_keys(row["foreign_keys"]),
                    columns=_parse_columns(row["fields"]),
                )
            )
    return tuple(sorted(tables, key=lambda table: (table.relation_kind, table.name)))


def get_schema_catalog() -> tuple[TableMetadata, ...]:
    return load_schema_catalog(str(discover_schema_metadata_path()))


def get_table_metadata(table_name: str) -> TableMetadata:
    for table in get_schema_catalog():
        if table.name == table_name:
            return table
    raise SchemaMetadataError(f"Unknown table in schema metadata: {table_name}")


def available_table_names() -> list[str]:
    return [table.name for table in get_schema_catalog()]
