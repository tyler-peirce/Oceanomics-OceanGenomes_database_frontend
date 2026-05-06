from datetime import date
from dataclasses import dataclass

from django.conf import settings
from django.db import DatabaseError, transaction

from .data_access import RelationPage, explorer_connection, fetch_row_detail, relation_reference
from .joined_views import fetch_joined_view_page
from .schema import get_table_metadata

RNA_EXTRACTION_TABLE_NAME = "rna_extraction"
TISSUE_TABLE_NAME = "tissue"
SAMPLE_TABLE_NAME = "sample"

RNA_EXTRACTION_LIST_COLUMNS = (
    "sample.og_num",
    "rna_extraction.tissue_id",
    "rna_extraction.ext_num",
    "rna_extraction.status",
    "rna_extraction.og_id",
    "rna_extraction.rna_id",
    "sample.nominal_species_id",
    "sample.common_name",
    "tissue.box",
    "rna_extraction.extraction_method",
    "rna_extraction.extraction_date",
    "rna_extraction.extraction_batch_id",
    "rna_extraction.qubit_conc",
    "rna_extraction.total_yield",
    "rna_extraction.rin",
    "rna_extraction.extraction_qc",
    "rna_extraction.status_overwrite",
)

RNA_EXTRACTION_COLUMN_LABELS = {
    "sample.og_num": "OG",
    "rna_extraction.tissue_id": "Sample ID",
    "rna_extraction.ext_num": "#",
    "rna_extraction.status": "Status",
    "rna_extraction.og_id": "Specimen ID",
    "rna_extraction.rna_id": "Tube ID",
    "sample.nominal_species_id": "Nominal Species ID",
    "sample.common_name": "Common Name/s",
    "tissue.box": "Tissue Box",
    "rna_extraction.extraction_method": "Extraction Method",
    "rna_extraction.extraction_date": "Extraction Date",
    "rna_extraction.extraction_batch_id": "Extraction Batch ID",
    "rna_extraction.final_buffer": "Final Buffer",
    "rna_extraction.volume": "Volume (uL)",
    "rna_extraction.qubit_conc": "Qubit Conc. (ng/uL)",
    "rna_extraction.nano_drop_conc": "NanoDrop Conc. (ng/uL)",
    "rna_extraction.ratio_260_280": "260/280",
    "rna_extraction.ratio_260_230": "260/230",
    "rna_extraction.total_yield": "Total Yield (ng)",
    "rna_extraction.tapestation_id": "TapeStation Run ID",
    "rna_extraction.rna_dv200": "RNA DV200",
    "rna_extraction.rin": "RIN",
    "rna_extraction.extraction_qc": "Pass / Fail QC",
    "rna_extraction.status_overwrite": "Overwrite Status",
    "rna_extraction.comment": "Comment",
    "rna_extraction.rna_freezer": "RNA Archives Freezer",
    "rna_extraction.rna_shelf": "Shelf",
    "rna_extraction.rna_rack": "Rack",
    "rna_extraction.rna_level": "Level",
    "rna_extraction.rna_box": "Box Label",
    "rna_extraction.rna_notes": "Notes",
}

WORKBOOK_UNMAPPED_RNA_FIELDS = (
    "gDNA? >7,000bp %",
    "Latest",
)


@dataclass(frozen=True)
class RnaExtractionFieldDefinition:
    name: str
    label: str
    required: bool = False
    help_text: str = ""
    widget: str = "text"
    group: str = "Core"


RNA_EXTRACTION_FIELD_DEFINITIONS = (
    RnaExtractionFieldDefinition(
        "tissue_id",
        "Sample ID",
        required=True,
        help_text="Use the tissue/sample ID from the Tissue worksheet. Specimen ID and Tube ID are derived from this.",
        group="Identity",
    ),
    RnaExtractionFieldDefinition(
        "ext_num",
        "#",
        required=True,
        widget="integer",
        help_text="Extraction number for this tissue. Tube ID is generated as Sample ID + _R or _R#.",
        group="Identity",
    ),
    RnaExtractionFieldDefinition("status", "Status", group="Workflow"),
    RnaExtractionFieldDefinition("extraction_method", "Extraction Method", group="Workflow"),
    RnaExtractionFieldDefinition("extraction_date", "Extraction Date", widget="date", group="Workflow"),
    RnaExtractionFieldDefinition("extraction_batch_id", "Extraction Batch ID", group="Workflow"),
    RnaExtractionFieldDefinition("final_buffer", "Final Buffer", group="Workflow"),
    RnaExtractionFieldDefinition("volume", "Volume (uL)", widget="integer", group="Workflow"),
    RnaExtractionFieldDefinition("qubit_conc", "Qubit Conc. (ng/uL)", widget="float", group="QC"),
    RnaExtractionFieldDefinition("nano_drop_conc", "NanoDrop Conc. (ng/uL)", widget="float", group="QC"),
    RnaExtractionFieldDefinition("ratio_260_280", "260/280", group="QC"),
    RnaExtractionFieldDefinition("ratio_260_230", "260/230", group="QC"),
    RnaExtractionFieldDefinition("total_yield", "Total Yield (ng)", widget="integer", group="QC"),
    RnaExtractionFieldDefinition("tapestation_id", "TapeStation Run ID", group="QC"),
    RnaExtractionFieldDefinition("rna_dv200", "RNA DV200", widget="float", group="QC"),
    RnaExtractionFieldDefinition("rin", "RIN", group="QC"),
    RnaExtractionFieldDefinition("extraction_qc", "Pass / Fail QC", group="QC"),
    RnaExtractionFieldDefinition("status_overwrite", "Overwrite Status", group="QC"),
    RnaExtractionFieldDefinition("comment", "Comment", widget="textarea", group="Comments"),
    RnaExtractionFieldDefinition("rna_freezer", "RNA Archives Freezer", group="Storage"),
    RnaExtractionFieldDefinition("rna_shelf", "Shelf", group="Storage"),
    RnaExtractionFieldDefinition("rna_rack", "Rack", group="Storage"),
    RnaExtractionFieldDefinition("rna_level", "Level", group="Storage"),
    RnaExtractionFieldDefinition("rna_box", "Box Label", group="Storage"),
    RnaExtractionFieldDefinition("rna_notes", "Notes", widget="textarea", group="Storage"),
)

RNA_EXTRACTION_CREATE_COLUMNS = tuple(field.name for field in RNA_EXTRACTION_FIELD_DEFINITIONS)
RNA_EXTRACTION_UPDATE_COLUMNS = tuple(
    field.name for field in RNA_EXTRACTION_FIELD_DEFINITIONS if field.name not in {"tissue_id", "ext_num"}
)
RNA_EXTRACTION_INLINE_EDITABLE_COLUMNS = (
    "status",
    "extraction_method",
    "extraction_date",
    "extraction_batch_id",
    "qubit_conc",
    "total_yield",
    "rin",
    "extraction_qc",
    "status_overwrite",
)
RNA_EXTRACTION_FIELD_DEFINITIONS_BY_NAME = {field.name: field for field in RNA_EXTRACTION_FIELD_DEFINITIONS}


def rna_extraction_field_groups():
    groups: dict[str, list[RnaExtractionFieldDefinition]] = {}
    for field in RNA_EXTRACTION_FIELD_DEFINITIONS:
        groups.setdefault(field.group, []).append(field)
    return tuple({"legend": legend, "fields": fields} for legend, fields in groups.items())


def rna_extraction_column_label(column_reference: str) -> str:
    return RNA_EXTRACTION_COLUMN_LABELS.get(column_reference, column_reference.replace("_", " ").title())


def fetch_rna_extraction_page(search_query: str = "", page_number: int = 1, page_size: int = 25) -> RelationPage:
    return fetch_joined_view_page(
        base_table_name=RNA_EXTRACTION_TABLE_NAME,
        visible_columns=list(RNA_EXTRACTION_LIST_COLUMNS),
        search_query=search_query,
        ordering="-rna_extraction.extraction_date",
        page_number=page_number,
        page_size=page_size,
    )


def fetch_rna_extraction_record(rna_id: str):
    return fetch_row_detail(get_table_metadata(RNA_EXTRACTION_TABLE_NAME), {"rna_id": rna_id})


def _quoted_identifier(name: str) -> str:
    return explorer_connection().ops.quote_name(name)


def _data_alias() -> str:
    return getattr(settings, "DATA_EXPLORER_DATABASE_ALIAS", "default")


def _normalized_values(cleaned_data: dict, columns: tuple[str, ...]) -> list:
    values = []
    for column_name in columns:
        value = cleaned_data.get(column_name)
        if value == "":
            value = None
        values.append(value)
    return values


def normalize_rna_extraction_field_value(column_name: str, raw_value):
    definition = RNA_EXTRACTION_FIELD_DEFINITIONS_BY_NAME[column_name]
    if raw_value in ("", None):
        return None
    if definition.widget == "date":
        return date.fromisoformat(str(raw_value))
    if definition.widget == "integer":
        return int(raw_value)
    if definition.widget == "float":
        return float(raw_value)
    return raw_value


def build_rna_id(tissue_id: str, ext_num: int) -> str:
    return f"{tissue_id}_R{ext_num}" if int(ext_num) > 1 else f"{tissue_id}_R"


def resolve_rna_identity(tissue_id: str, ext_num: int) -> dict:
    tissue_row, tissue_error = fetch_row_detail(get_table_metadata(TISSUE_TABLE_NAME), {"tissue_id": tissue_id})
    if tissue_error or not tissue_row:
        raise DatabaseError(f"Tissue {tissue_id} was not found in the Tissue worksheet tables.")

    og_id = tissue_row.get("og_id")
    if not og_id:
        raise DatabaseError(f"Tissue {tissue_id} does not have a linked specimen ID (og_id).")

    sample_row = None
    sample_error = None
    if og_id:
        sample_row, sample_error = fetch_row_detail(get_table_metadata(SAMPLE_TABLE_NAME), {"og_id": og_id})

    return {
        "og_id": og_id,
        "rna_id": build_rna_id(tissue_id, ext_num),
        "tissue": tissue_row,
        "sample": sample_row,
        "sample_error": sample_error,
    }


def create_rna_extraction_record(cleaned_data: dict) -> tuple[str, str]:
    table = get_table_metadata(RNA_EXTRACTION_TABLE_NAME)
    ext_num = int(cleaned_data["ext_num"])
    identity = resolve_rna_identity(cleaned_data["tissue_id"], ext_num)
    columns = ("rna_id", "og_id", *RNA_EXTRACTION_CREATE_COLUMNS)
    values = _normalized_values(cleaned_data, RNA_EXTRACTION_CREATE_COLUMNS)

    with transaction.atomic(using=_data_alias()):
        with explorer_connection().cursor() as cursor:
            placeholders = ", ".join(["%s"] * len(columns))
            sql = (
                f"INSERT INTO {relation_reference(table)} "
                f"({', '.join(_quoted_identifier(column) for column in columns)}) "
                f"VALUES ({placeholders})"
            )
            cursor.execute(sql, [identity["rna_id"], identity["og_id"], *values])

    return identity["rna_id"], identity["og_id"]


def update_rna_extraction_record(rna_id: str, cleaned_data: dict) -> None:
    table = get_table_metadata(RNA_EXTRACTION_TABLE_NAME)
    assignments = ", ".join(f"{_quoted_identifier(column)} = %s" for column in RNA_EXTRACTION_UPDATE_COLUMNS)
    sql = (
        f"UPDATE {relation_reference(table)} "
        f"SET {assignments} "
        f"WHERE {_quoted_identifier('rna_id')} = %s"
    )

    with transaction.atomic(using=_data_alias()):
        with explorer_connection().cursor() as cursor:
            cursor.execute(sql, [*_normalized_values(cleaned_data, RNA_EXTRACTION_UPDATE_COLUMNS), rna_id])
            if cursor.rowcount != 1:
                raise DatabaseError(f"Expected to update one RNA extraction row for {rna_id}, updated {cursor.rowcount}.")


def bulk_update_rna_extractions(rows: list[dict]) -> int:
    table = get_table_metadata(RNA_EXTRACTION_TABLE_NAME)
    updated_count = 0

    with transaction.atomic(using=_data_alias()):
        with explorer_connection().cursor() as cursor:
            for row in rows:
                rna_id = row.get("id")
                raw_changes = row.get("changes") or {}
                if not rna_id:
                    raise DatabaseError("Missing RNA tube ID for bulk RNA extraction update.")

                invalid_columns = sorted(set(raw_changes) - set(RNA_EXTRACTION_INLINE_EDITABLE_COLUMNS))
                if invalid_columns:
                    raise DatabaseError(
                        "Unsupported inline RNA extraction columns: " + ", ".join(invalid_columns)
                    )

                if not raw_changes:
                    continue

                assignments = []
                params = []
                for column_name, raw_value in raw_changes.items():
                    assignments.append(f"{_quoted_identifier(column_name)} = %s")
                    params.append(normalize_rna_extraction_field_value(column_name, raw_value))

                sql = (
                    f"UPDATE {relation_reference(table)} "
                    f"SET {', '.join(assignments)} "
                    f"WHERE {_quoted_identifier('rna_id')} = %s"
                )
                cursor.execute(sql, [*params, rna_id])
                if cursor.rowcount != 1:
                    raise DatabaseError(f"Expected to update one RNA extraction row for {rna_id}, updated {cursor.rowcount}.")
                updated_count += 1

    return updated_count
