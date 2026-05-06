from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.db import DatabaseError, connections
from django.urls import reverse

from .schema import TableMetadata


@dataclass(frozen=True)
class RelationPage:
    rows: list[dict[str, Any]]
    total_count: int
    error: str | None = None


def explorer_connection():
    return connections[getattr(settings, "DATA_EXPLORER_DATABASE_ALIAS", "default")]


def _quote_identifier(name: str) -> str:
    return explorer_connection().ops.quote_name(name)


def relation_reference(table: TableMetadata) -> str:
    if explorer_connection().vendor == "postgresql":
        return f"{_quote_identifier(table.schema)}.{_quote_identifier(table.name)}"
    return _quote_identifier(table.name)


def _normalize_ordering(table: TableMetadata, ordering: str | None) -> tuple[str | None, str]:
    allowed_columns = set(table.ordered_column_names)
    requested = ordering or table.default_ordering
    direction = "ASC"
    column_name = requested or None
    if requested and requested.startswith("-"):
        direction = "DESC"
        column_name = requested[1:]
    if not column_name or column_name not in allowed_columns:
        column_name = table.default_ordering or None
        direction = "ASC"
    return column_name, direction


def fetch_relation_page(
    table: TableMetadata,
    visible_columns: list[str],
    search_query: str = "",
    ordering: str | None = None,
    page_number: int = 1,
    page_size: int = 25,
) -> RelationPage:
    selected_columns = [column for column in visible_columns if column in table.ordered_column_names]
    if not selected_columns:
        selected_columns = table.default_visible_columns

    where_parts = []
    where_params: list[Any] = []
    if search_query:
        lowered_query = f"%{search_query.lower()}%"
        search_clauses = []
        for column_name in table.searchable_columns:
            search_clauses.append(f"LOWER(CAST({_quote_identifier(column_name)} AS TEXT)) LIKE %s")
            where_params.append(lowered_query)
        if search_clauses:
            where_parts.append("(" + " OR ".join(search_clauses) + ")")

    where_sql = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""
    order_column, order_direction = _normalize_ordering(table, ordering)
    order_sql = (
        f" ORDER BY {_quote_identifier(order_column)} {order_direction}" if order_column else ""
    )
    limit = max(page_size, 1)
    offset = max(page_number - 1, 0) * limit

    count_sql = f"SELECT COUNT(*) FROM {relation_reference(table)}{where_sql}"
    data_sql = (
        "SELECT "
        + ", ".join(_quote_identifier(column_name) for column_name in selected_columns)
        + f" FROM {relation_reference(table)}{where_sql}{order_sql} LIMIT %s OFFSET %s"
    )

    try:
        with explorer_connection().cursor() as cursor:
            cursor.execute(count_sql, where_params)
            total_count = int(cursor.fetchone()[0])
            cursor.execute(data_sql, [*where_params, limit, offset])
            column_names = [description[0] for description in cursor.description]
            rows = [dict(zip(column_names, row)) for row in cursor.fetchall()]
    except DatabaseError as exc:
        return RelationPage(rows=[], total_count=0, error=str(exc))

    return RelationPage(rows=rows, total_count=total_count)


def fetch_row_detail(table: TableMetadata, key_pairs: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    if not table.primary_key_columns:
        return None, "This relation does not expose a primary key in the exported metadata."

    where_parts = []
    params: list[Any] = []
    for column_name in table.primary_key_columns:
        value = key_pairs.get(column_name)
        if value is None:
            return None, f"Missing key value for {column_name}."
        where_parts.append(f"CAST({_quote_identifier(column_name)} AS TEXT) = %s")
        params.append(value)

    sql = (
        "SELECT "
        + ", ".join(_quote_identifier(column_name) for column_name in table.ordered_column_names)
        + f" FROM {relation_reference(table)} WHERE {' AND '.join(where_parts)} LIMIT 1"
    )

    try:
        with explorer_connection().cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            if row is None:
                return None, "No row matched the selected primary key."
            column_names = [description[0] for description in cursor.description]
            return dict(zip(column_names, row)), None
    except DatabaseError as exc:
        return None, str(exc)


def count_relation_rows(table: TableMetadata) -> int | None:
    try:
        with explorer_connection().cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {relation_reference(table)}")
            return int(cursor.fetchone()[0])
    except DatabaseError:
        return None


def build_row_detail_url(table: TableMetadata, row: dict[str, Any]) -> str | None:
    if not table.primary_key_columns:
        return None

    key_values = {}
    for column_name in table.primary_key_columns:
        value = row.get(column_name)
        if value is None:
            return None
        key_values[column_name] = str(value)

    return reverse("table_row_detail", kwargs={"table_name": table.name}) + "?" + urlencode(key_values)
