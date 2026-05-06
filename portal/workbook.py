from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class WorksheetTabDefinition:
    slug: str
    label: str
    table_name: str | None = None
    preset_slug: str | None = None
    route_name: str | None = None


WORKSHEET_TABS = (
    WorksheetTabDefinition("summary", "Summary", table_name="summary", preset_slug="programme-summary"),
    WorksheetTabDefinition("metadata", "1.MetaData", route_name="worksheet_metadata"),
    WorksheetTabDefinition("tissue", "2.Tissue", table_name="tissue", preset_slug="tissue-inventory"),
    WorksheetTabDefinition("rna_extractions", "3.RNAExtractions", route_name="worksheet_rna_extractions"),
    WorksheetTabDefinition("dna_extractions", "3.DNAExtractions", table_name="dna_extraction", preset_slug="dna-extraction-queue"),
    WorksheetTabDefinition("pacbio", "4.PacBio", table_name="pacbio_library"),
    WorksheetTabDefinition("illumina", "4.Illumina", table_name="illumina_library", preset_slug="illumina-library-board"),
    WorksheetTabDefinition("ont", "4.ONT", table_name="ont_library"),
    WorksheetTabDefinition("rna_illumina", "4.RNAIllumina", table_name="rna_library_ilmn"),
    WorksheetTabDefinition("hic_lysate", "4.HiCLysate", table_name="hic_lysate"),
    WorksheetTabDefinition("hic_library", "4.HiCLibrary", table_name="hic_library"),
    WorksheetTabDefinition("rna_kinnex", "4.RNAkinnex", table_name="rna_library_kinx"),
    WorksheetTabDefinition("sequencing", "5.Sequencing", table_name="sequencing", preset_slug="sequencing-runs"),
)


def build_worksheet_tabs(active_slug: str | None = None) -> list[dict]:
    tabs = []
    for tab in WORKSHEET_TABS:
        if tab.route_name:
            url = reverse(tab.route_name)
        else:
            url = reverse("table_detail", kwargs={"table_name": tab.table_name})
            if tab.preset_slug:
                url += f"?preset={tab.preset_slug}"

        tabs.append(
            {
                "slug": tab.slug,
                "label": tab.label,
                "url": url,
                "is_active": tab.slug == active_slug,
            }
        )
    return tabs


def detect_active_worksheet(table_name: str, preset_slug: str | None = None) -> str | None:
    if table_name == "sample":
        return "metadata"
    if table_name == "rna_extraction":
        return "rna_extractions"

    for tab in WORKSHEET_TABS:
        if tab.table_name != table_name:
            continue
        if tab.preset_slug and preset_slug and tab.preset_slug == preset_slug:
            return tab.slug
        if tab.preset_slug is None:
            return tab.slug

    return None
