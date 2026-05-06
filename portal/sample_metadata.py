from datetime import date
from dataclasses import dataclass

from django.conf import settings
from django.db import DatabaseError, transaction

from .data_access import RelationPage, explorer_connection, fetch_relation_page, fetch_row_detail, relation_reference
from .schema import get_table_metadata

SAMPLE_TABLE_NAME = "sample"

SAMPLE_LIST_COLUMNS = (
    "og_num",
    "og_id",
    "project_id",
    "field_id",
    "nominal_species_id",
    "common_name",
    "collector",
    "date_collected",
    "location",
    "sample_condition",
)

SAMPLE_COLUMN_LABELS = {
    "og_num": "OG",
    "og_id": "Specimen ID",
    "project_id": "Project ID",
    "field_id": "Field Identifier",
    "nominal_species_id": "Nominal Species ID",
    "common_name": "Common name/s",
    "collector": "Collector",
    "contact": "Contact",
    "date_collected": "Date Collected",
    "sex": "Sex",
    "weight": "Weight (g)",
    "lengthtl_and_lengthfl": "Length (TL or FL mm)",
    "country": "Country",
    "state": "State",
    "location": "Location",
    "latitude_collection": "Latitude Collection",
    "longitude_collection": "Longitude Collection",
    "depth_collection": "Depth Collection (m)",
    "collection_method": "Collection Method",
    "preservation_method": "Preservation Method",
    "sample_condition": "Sample Condition",
    "photo_voucher": "Photo Voucher",
    "photo_id": "Photo Voucher Accession Details",
    "specimen_voucher": "Specimen Voucher",
    "voucher_id": "Specimen Voucher Accession Details",
    "comments": "Comments",
}

WORKBOOK_UNMAPPED_METADATA_FIELDS = (
    "Sample Condition upon preservation",
    "Ethics Permit",
    "Collection Permit",
    "Import Permit",
    "Cultural Significance",
    "CITES",
    "CMS",
    "IUCN",
    "EPBC",
    "Sample Receipt Date",
)


@dataclass(frozen=True)
class SampleFieldDefinition:
    name: str
    label: str
    required: bool = False
    help_text: str = ""
    widget: str = "text"
    group: str = "Core"


SAMPLE_FIELD_DEFINITIONS = (
    SampleFieldDefinition("project_id", "Project ID", group="Identity"),
    SampleFieldDefinition("field_id", "Field Identifier", group="Identity"),
    SampleFieldDefinition("nominal_species_id", "Nominal Species ID", group="Identity"),
    SampleFieldDefinition("common_name", "Common name/s", group="Identity"),
    SampleFieldDefinition("collector", "Collector", group="Identity"),
    SampleFieldDefinition("contact", "Contact", group="Identity"),
    SampleFieldDefinition("date_collected", "Date Collected", widget="date", group="Collection"),
    SampleFieldDefinition("sex", "Sex", group="Collection"),
    SampleFieldDefinition("weight", "Weight (g)", group="Collection"),
    SampleFieldDefinition("lengthtl_and_lengthfl", "Length (TL or FL mm)", group="Collection"),
    SampleFieldDefinition("country", "Country", group="Collection"),
    SampleFieldDefinition("state", "State", group="Collection"),
    SampleFieldDefinition("location", "Location", group="Collection"),
    SampleFieldDefinition("latitude_collection", "Latitude Collection", group="Collection"),
    SampleFieldDefinition("longitude_collection", "Longitude Collection", group="Collection"),
    SampleFieldDefinition("depth_collection", "Depth Collection (m)", group="Collection"),
    SampleFieldDefinition("collection_method", "Collection Method", group="Collection"),
    SampleFieldDefinition("preservation_method", "Preservation Method", group="Condition"),
    SampleFieldDefinition("sample_condition", "Sample Condition", group="Condition"),
    SampleFieldDefinition("photo_voucher", "Photo Voucher", group="Vouchering"),
    SampleFieldDefinition("photo_id", "Photo Voucher Accession Details", group="Vouchering"),
    SampleFieldDefinition("specimen_voucher", "Specimen Voucher", group="Vouchering"),
    SampleFieldDefinition("voucher_id", "Specimen Voucher Accession Details", group="Vouchering"),
    SampleFieldDefinition("comments", "Comments", widget="textarea", group="Notes"),
)

SAMPLE_EDITABLE_COLUMNS = tuple(field.name for field in SAMPLE_FIELD_DEFINITIONS)
SAMPLE_INLINE_EDITABLE_COLUMNS = (
    "project_id",
    "field_id",
    "nominal_species_id",
    "common_name",
    "collector",
    "date_collected",
    "location",
    "sample_condition",
)
SAMPLE_FIELD_DEFINITIONS_BY_NAME = {field.name: field for field in SAMPLE_FIELD_DEFINITIONS}


def sample_field_groups():
    groups: dict[str, list[SampleFieldDefinition]] = {}
    for field in SAMPLE_FIELD_DEFINITIONS:
        groups.setdefault(field.group, []).append(field)
    return tuple({"legend": legend, "fields": fields} for legend, fields in groups.items())


def sample_column_label(column_name: str) -> str:
    return SAMPLE_COLUMN_LABELS.get(column_name, column_name.replace("_", " ").title())


def fetch_sample_metadata_page(search_query: str = "", page_number: int = 1, page_size: int = 25) -> RelationPage:
    return fetch_relation_page(
        table=get_table_metadata(SAMPLE_TABLE_NAME),
        visible_columns=list(SAMPLE_LIST_COLUMNS),
        search_query=search_query,
        ordering="-og_num",
        page_number=page_number,
        page_size=page_size,
    )


def fetch_sample_metadata_record(og_id: str):
    return fetch_row_detail(get_table_metadata(SAMPLE_TABLE_NAME), {"og_id": og_id})


def _normalized_values(cleaned_data: dict) -> list:
    values = []
    for column_name in SAMPLE_EDITABLE_COLUMNS:
        value = cleaned_data.get(column_name)
        if value == "":
            value = None
        values.append(value)
    return values


def normalize_sample_field_value(column_name: str, raw_value):
    definition = SAMPLE_FIELD_DEFINITIONS_BY_NAME[column_name]
    if raw_value in ("", None):
        return None
    if definition.widget == "date":
        return date.fromisoformat(str(raw_value))
    return raw_value


def _quoted_identifier(name: str) -> str:
    return explorer_connection().ops.quote_name(name)


def _data_alias() -> str:
    return getattr(settings, "DATA_EXPLORER_DATABASE_ALIAS", "default")


def create_sample_metadata_record(cleaned_data: dict) -> tuple[int, str]:
    table = get_table_metadata(SAMPLE_TABLE_NAME)
    columns = ("og_num", "og_id", *SAMPLE_EDITABLE_COLUMNS)
    values = _normalized_values(cleaned_data)

    with transaction.atomic(using=_data_alias()):
        with explorer_connection().cursor() as cursor:
            if explorer_connection().vendor == "postgresql":
                cursor.execute(f"LOCK TABLE {relation_reference(table)} IN EXCLUSIVE MODE")

            cursor.execute(f"SELECT COALESCE(MAX({_quoted_identifier('og_num')}), 0) + 1 FROM {relation_reference(table)}")
            next_og_num = int(cursor.fetchone()[0] or 1)
            next_og_id = f"OG{next_og_num}"

            placeholders = ", ".join(["%s"] * len(columns))
            sql = (
                f"INSERT INTO {relation_reference(table)} "
                f"({', '.join(_quoted_identifier(column) for column in columns)}) "
                f"VALUES ({placeholders})"
            )
            cursor.execute(sql, [next_og_num, next_og_id, *values])

    return next_og_num, next_og_id


def update_sample_metadata_record(og_id: str, cleaned_data: dict) -> None:
    table = get_table_metadata(SAMPLE_TABLE_NAME)
    assignments = ", ".join(f"{_quoted_identifier(column)} = %s" for column in SAMPLE_EDITABLE_COLUMNS)
    sql = (
        f"UPDATE {relation_reference(table)} "
        f"SET {assignments} "
        f"WHERE {_quoted_identifier('og_id')} = %s"
    )

    with transaction.atomic(using=_data_alias()):
        with explorer_connection().cursor() as cursor:
            cursor.execute(sql, [*_normalized_values(cleaned_data), og_id])
            if cursor.rowcount != 1:
                raise DatabaseError(f"Expected to update one sample row for {og_id}, updated {cursor.rowcount}.")


def bulk_update_sample_metadata(rows: list[dict]) -> int:
    table = get_table_metadata(SAMPLE_TABLE_NAME)
    updated_count = 0

    with transaction.atomic(using=_data_alias()):
        with explorer_connection().cursor() as cursor:
            for row in rows:
                og_id = row.get("id")
                raw_changes = row.get("changes") or {}
                if not og_id:
                    raise DatabaseError("Missing specimen ID for bulk sample update.")

                invalid_columns = sorted(set(raw_changes) - set(SAMPLE_INLINE_EDITABLE_COLUMNS))
                if invalid_columns:
                    raise DatabaseError(
                        "Unsupported inline sample columns: " + ", ".join(invalid_columns)
                    )

                if not raw_changes:
                    continue

                assignments = []
                params = []
                for column_name, raw_value in raw_changes.items():
                    assignments.append(f"{_quoted_identifier(column_name)} = %s")
                    params.append(normalize_sample_field_value(column_name, raw_value))

                sql = (
                    f"UPDATE {relation_reference(table)} "
                    f"SET {', '.join(assignments)} "
                    f"WHERE {_quoted_identifier('og_id')} = %s"
                )
                cursor.execute(sql, [*params, og_id])
                if cursor.rowcount != 1:
                    raise DatabaseError(f"Expected to update one sample row for {og_id}, updated {cursor.rowcount}.")
                updated_count += 1

    return updated_count
