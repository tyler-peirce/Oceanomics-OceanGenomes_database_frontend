from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from django.db import DatabaseError

from .data_access import RelationPage, explorer_connection, relation_reference
from .schema import SchemaMetadataError, TableMetadata, get_table_metadata


@dataclass(frozen=True)
class JoinPathStep:
    from_table_name: str
    to_table_name: str
    fk_columns: tuple[str, ...]
    reference_columns: tuple[str, ...]
    constraint_name: str


def column_reference(table_name: str, column_name: str) -> str:
    return f"{table_name}.{column_name}"


def parse_column_reference(reference: str) -> tuple[str, str]:
    if "." not in reference:
        raise SchemaMetadataError(f"Invalid joined-view column reference: {reference}")
    table_name, column_name = reference.split(".", 1)
    return table_name, column_name


def output_alias(reference: str) -> str:
    table_name, column_name = parse_column_reference(reference)
    return f"{table_name}__{column_name}"


def hidden_base_pk_alias(column_name: str) -> str:
    return f"__basepk__{column_name}"


def _quote_identifier(name: str) -> str:
    return explorer_connection().ops.quote_name(name)


@lru_cache(maxsize=64)
def reachable_parent_paths(base_table_name: str) -> dict[str, tuple[JoinPathStep, ...]]:
    get_table_metadata(base_table_name)

    paths: dict[str, tuple[JoinPathStep, ...]] = {base_table_name: ()}
    queue: deque[str] = deque([base_table_name])

    while queue:
        current_table_name = queue.popleft()
        current_table = get_table_metadata(current_table_name)
        current_path = paths[current_table_name]

        for foreign_key in current_table.foreign_keys:
            target_table_name = foreign_key.reference_table
            try:
                get_table_metadata(target_table_name)
            except SchemaMetadataError:
                continue

            if target_table_name in paths:
                continue

            paths[target_table_name] = (
                *current_path,
                JoinPathStep(
                    from_table_name=current_table_name,
                    to_table_name=target_table_name,
                    fk_columns=foreign_key.columns,
                    reference_columns=foreign_key.reference_columns,
                    constraint_name=foreign_key.constraint_name,
                ),
            )
            queue.append(target_table_name)

    paths.pop(base_table_name, None)
    return paths


def accessible_joined_tables(base_table_name: str) -> list[TableMetadata]:
    base_table = get_table_metadata(base_table_name)
    parent_paths = reachable_parent_paths(base_table_name)
    related_tables = [
        get_table_metadata(table_name)
        for table_name, _path in sorted(parent_paths.items(), key=lambda item: (len(item[1]), item[0]))
    ]
    return [base_table, *related_tables]


@lru_cache(maxsize=64)
def joined_view_column_choices(base_table_name: str) -> tuple[tuple[str, str], ...]:
    choices = []
    for table in accessible_joined_tables(base_table_name):
        table_prefix = f"{table.name} (base)" if table.name == base_table_name else table.name
        for column in table.columns:
            flags = [column.data_type]
            if column.is_primary_key:
                flags.append("PK")
            elif not column.is_nullable:
                flags.append("required")
            choices.append(
                (
                    column_reference(table.name, column.column_name),
                    f"[{table_prefix}] {column.column_name} | {' | '.join(flags)}",
                )
            )
    return tuple(choices)


def available_joined_column_references(base_table_name: str) -> set[str]:
    return {value for value, _label in joined_view_column_choices(base_table_name)}


def default_joined_visible_columns(base_table_name: str) -> list[str]:
    table = get_table_metadata(base_table_name)
    return [column_reference(base_table_name, column_name) for column_name in table.default_visible_columns]


def default_joined_ordering(base_table_name: str) -> str:
    table = get_table_metadata(base_table_name)
    if not table.default_ordering:
        return ""
    return column_reference(base_table_name, table.default_ordering)


@lru_cache(maxsize=64)
def joined_view_ordering_choices(base_table_name: str) -> tuple[tuple[str, str], ...]:
    choices: list[tuple[str, str]] = [("", "Natural order")]
    for reference, _label in joined_view_column_choices(base_table_name):
        choices.append((reference, f"{reference} (ascending)"))
        choices.append((f"-{reference}", f"{reference} (descending)"))
    return tuple(choices)


def joined_view_display_columns(base_table_name: str, visible_columns: list[str]) -> list[dict[str, str]]:
    available = available_joined_column_references(base_table_name)
    columns = []
    for reference in visible_columns:
        if reference not in available:
            continue
        table_name, column_name = parse_column_reference(reference)
        label = column_name if table_name == base_table_name else reference
        columns.append(
            {
                "reference": reference,
                "key": output_alias(reference),
                "label": label,
            }
        )
    return columns


def _normalize_ordering(base_table_name: str, ordering: str | None) -> tuple[str | None, str]:
    available = available_joined_column_references(base_table_name)
    requested = ordering or default_joined_ordering(base_table_name)
    direction = "ASC"
    reference = requested or None

    if reference and reference.startswith("-"):
        direction = "DESC"
        reference = reference[1:]

    if not reference or reference not in available:
        reference = default_joined_ordering(base_table_name) or None
        direction = "ASC"

    return reference, direction


def _join_plan(base_table_name: str, required_table_names: list[str]) -> tuple[dict[str, str], str]:
    aliases = {base_table_name: "t0"}
    joins: list[str] = []
    next_alias = 1
    parent_paths = reachable_parent_paths(base_table_name)

    for table_name in required_table_names:
        if table_name == base_table_name:
            continue

        path = parent_paths[table_name]
        for step in path:
            if step.to_table_name in aliases:
                continue

            from_alias = aliases[step.from_table_name]
            to_alias = f"t{next_alias}"
            next_alias += 1
            aliases[step.to_table_name] = to_alias

            target_table = get_table_metadata(step.to_table_name)
            join_conditions = " AND ".join(
                f"{from_alias}.{_quote_identifier(fk_column)} = {to_alias}.{_quote_identifier(reference_column)}"
                for fk_column, reference_column in zip(step.fk_columns, step.reference_columns)
            )
            joins.append(f" LEFT JOIN {relation_reference(target_table)} {to_alias} ON {join_conditions}")

    return aliases, "".join(joins)


def fetch_joined_view_page(
    base_table_name: str,
    visible_columns: list[str],
    search_query: str = "",
    ordering: str | None = None,
    page_number: int = 1,
    page_size: int = 25,
) -> RelationPage:
    base_table = get_table_metadata(base_table_name)
    display_columns = joined_view_display_columns(base_table_name, visible_columns)
    if not display_columns:
        display_columns = joined_view_display_columns(base_table_name, default_joined_visible_columns(base_table_name))

    ordering_reference, order_direction = _normalize_ordering(base_table_name, ordering)
    required_tables = [base_table_name]

    for column in display_columns:
        table_name, _column_name = parse_column_reference(column["reference"])
        if table_name not in required_tables:
            required_tables.append(table_name)

    if ordering_reference:
        ordering_table_name, _ordering_column_name = parse_column_reference(ordering_reference)
        if ordering_table_name not in required_tables:
            required_tables.append(ordering_table_name)

    aliases, join_sql = _join_plan(base_table_name, required_tables)

    select_parts = [
        (
            f"{aliases[parse_column_reference(column['reference'])[0]]}."
            f"{_quote_identifier(parse_column_reference(column['reference'])[1])} "
            f"AS {_quote_identifier(column['key'])}"
        )
        for column in display_columns
    ]

    for primary_key in base_table.primary_key_columns:
        select_parts.append(
            f"{aliases[base_table_name]}.{_quote_identifier(primary_key)} "
            f"AS {_quote_identifier(hidden_base_pk_alias(primary_key))}"
        )

    where_parts = []
    where_params: list[Any] = []
    if search_query:
        lowered_query = f"%{search_query.lower()}%"
        search_clauses = []
        for column in display_columns:
            table_name, column_name = parse_column_reference(column["reference"])
            search_clauses.append(
                f"LOWER(CAST({aliases[table_name]}.{_quote_identifier(column_name)} AS TEXT)) LIKE %s"
            )
            where_params.append(lowered_query)
        if search_clauses:
            where_parts.append("(" + " OR ".join(search_clauses) + ")")

    where_sql = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""

    order_sql = ""
    if ordering_reference:
        ordering_table_name, ordering_column_name = parse_column_reference(ordering_reference)
        order_sql = (
            f" ORDER BY {aliases[ordering_table_name]}.{_quote_identifier(ordering_column_name)} {order_direction}"
        )

    limit = max(page_size, 1)
    offset = max(page_number - 1, 0) * limit
    from_sql = f" FROM {relation_reference(base_table)} {aliases[base_table_name]}{join_sql}"

    count_sql = f"SELECT COUNT(*){from_sql}{where_sql}"
    data_sql = (
        "SELECT "
        + ", ".join(select_parts)
        + from_sql
        + where_sql
        + order_sql
        + " LIMIT %s OFFSET %s"
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
