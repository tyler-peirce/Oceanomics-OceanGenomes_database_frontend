from dataclasses import dataclass, replace

from .schema import SchemaMetadataError, get_table_metadata


@dataclass(frozen=True)
class LabWorkflowPreset:
    slug: str
    name: str
    table_name: str
    category: str
    description: str
    visible_columns: tuple[str, ...]
    ordering: str = ""
    featured: bool = False


PRESET_DEFINITIONS = (
    LabWorkflowPreset(
        slug="specimen-intake",
        name="Specimen Intake",
        table_name="sample",
        category="Intake",
        description="Core specimen identity, collection, and operational intake fields.",
        visible_columns=(
            "og_id",
            "field_id",
            "project_id",
            "nominal_species_id",
            "common_name",
            "collector",
            "date_collected",
            "location",
            "sample_condition",
            "priority",
            "workflow",
            "extraction_queue",
            "summary_comments",
            "embargo_status",
        ),
        ordering="priority",
        featured=True,
    ),
    LabWorkflowPreset(
        slug="sequencing-readiness",
        name="Sequencing Readiness",
        table_name="sample",
        category="Planning",
        description="Quick readiness board for extraction, library prep, and sequencing pathways.",
        visible_columns=(
            "og_id",
            "common_name",
            "priority",
            "workflow",
            "tissues",
            "extracted",
            "ilmn",
            "il_status",
            "hifi",
            "pb_status",
            "hic",
            "hic_status",
            "nano",
            "ont_num",
            "rna",
            "rna_status",
        ),
        ordering="priority",
        featured=True,
    ),
    LabWorkflowPreset(
        slug="tissue-inventory",
        name="Tissue Inventory",
        table_name="tissue",
        category="Inventory",
        description="Physical storage view for tissue location and extraction state.",
        visible_columns=(
            "tissue_id",
            "og_id",
            "field_id",
            "alt_id",
            "tissue",
            "extracted",
            "freezer",
            "shelf",
            "rack",
            "level",
            "box",
            "comment",
        ),
        ordering="og_id",
        featured=True,
    ),
    LabWorkflowPreset(
        slug="dna-extraction-queue",
        name="DNA Extraction Queue",
        table_name="dna_extraction",
        category="Extraction",
        description="DNA extraction tracking with QC and storage context.",
        visible_columns=(
            "dna_id",
            "og_id",
            "tissue_id",
            "ext_num",
            "status",
            "extraction_method",
            "extraction_date",
            "extraction_batch_id",
            "qubit_conc",
            "nano_drop_conc",
            "total_yield",
            "extraction_qc",
            "dna_freezer",
            "dna_box",
            "status_overwrite",
        ),
        ordering="-extraction_date",
        featured=True,
    ),
    LabWorkflowPreset(
        slug="rna-extraction-queue",
        name="RNA Extraction Queue",
        table_name="rna_extraction",
        category="Extraction",
        description="RNA extraction and integrity tracking for downstream library prep.",
        visible_columns=(
            "rna_id",
            "og_id",
            "tissue_id",
            "ext_num",
            "status",
            "extraction_method",
            "extraction_date",
            "qubit_conc",
            "total_yield",
            "rin",
            "rna_dv200",
            "extraction_qc",
            "rna_freezer",
            "rna_box",
            "status_overwrite",
        ),
        ordering="-extraction_date",
        featured=True,
    ),
    LabWorkflowPreset(
        slug="illumina-library-board",
        name="Illumina Library Board",
        table_name="illumina_library",
        category="Libraries",
        description="Library prep status for Illumina-ready material.",
        visible_columns=(
            "illumina_library_tube_id",
            "og_id",
            "dna_id",
            "ilmn_num",
            "ilmn_status",
            "library_method",
            "library_date",
            "library_id",
            "index_set",
            "index_well",
            "library_qubit_conc",
            "status_overwrite",
        ),
        ordering="-library_date",
        featured=False,
    ),
    LabWorkflowPreset(
        slug="sequencing-runs",
        name="Sequencing Runs",
        table_name="sequencing",
        category="Sequencing",
        description="Operational run tracker across technologies and instruments.",
        visible_columns=(
            "sequencing_id",
            "og_id",
            "technology",
            "instrument",
            "run_date",
            "run_id",
            "seq_date",
            "cell_id",
            "smrt_num",
            "seq_type",
            "design_no",
            "seq_comments",
        ),
        ordering="-seq_date",
        featured=True,
    ),
    LabWorkflowPreset(
        slug="qc-snapshot",
        name="QC Snapshot",
        table_name="raw_qc",
        category="QC",
        description="High-level genome and contamination metrics per OG sample.",
        visible_columns=(
            "og_id",
            "genomesize",
            "homozygosity",
            "heterozygosity",
            "repeatsize",
            "uniquesize",
            "modelfit",
            "errorrate",
            "contam_reads",
        ),
        ordering="og_id",
        featured=False,
    ),
    LabWorkflowPreset(
        slug="programme-summary",
        name="Programme Summary",
        table_name="summary",
        category="Programme",
        description="Cross-workflow management view for end-to-end status tracking.",
        visible_columns=(
            "og_id",
            "project_id",
            "workflow",
            "priority",
            "common_name",
            "collector",
            "tissues",
            "extracted",
            "dna_extraction_status",
            "illumina_status",
            "pacbio_status",
            "hic_status",
            "nanopore_status",
            "rna_extraction_status",
            "rna_ilmn_status",
            "rna_kinnex_status",
            "summary_comments",
        ),
        ordering="og_id",
        featured=True,
    ),
)


def _validated_preset(preset: LabWorkflowPreset) -> LabWorkflowPreset | None:
    try:
        table = get_table_metadata(preset.table_name)
    except SchemaMetadataError:
        return None

    visible_columns = tuple(
        column_name for column_name in preset.visible_columns if column_name in table.ordered_column_names
    )
    if not visible_columns:
        visible_columns = tuple(table.default_visible_columns)

    ordering = preset.ordering
    ordering_column = ordering[1:] if ordering.startswith("-") else ordering
    if ordering_column and ordering_column not in table.ordered_column_names:
        ordering = table.default_ordering

    return replace(preset, visible_columns=visible_columns, ordering=ordering)


def get_lab_presets() -> list[LabWorkflowPreset]:
    presets = []
    for preset in PRESET_DEFINITIONS:
        validated = _validated_preset(preset)
        if validated is not None:
            presets.append(validated)
    return presets


def get_featured_lab_presets() -> list[LabWorkflowPreset]:
    return [preset for preset in get_lab_presets() if preset.featured]


def get_lab_preset(slug: str) -> LabWorkflowPreset | None:
    for preset in get_lab_presets():
        if preset.slug == slug:
            return preset
    return None


def get_table_lab_presets(table_name: str) -> list[LabWorkflowPreset]:
    return [preset for preset in get_lab_presets() if preset.table_name == table_name]
