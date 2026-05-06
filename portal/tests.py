import csv
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings

from .models import SavedJoinedView, SavedTableView
from .schema import load_schema_catalog


def _field(
    column_name,
    data_type="text",
    postgres_type="text",
    is_nullable=True,
    is_primary_key=False,
    ordinal_position=1,
):
    return {
        "default": None,
        "data_type": data_type,
        "max_length": None,
        "column_name": column_name,
        "enum_values": None,
        "is_nullable": is_nullable,
        "numeric_scale": None,
        "postgres_type": postgres_type,
        "is_primary_key": is_primary_key,
        "ordinal_position": ordinal_position,
        "numeric_precision": None,
        "datetime_precision": None,
        "foreign_key_membership": [],
        "is_in_unique_constraint": False,
        "unique_constraint_membership": [],
    }


def _sample_fields():
    return [
        _field("og_id", is_nullable=False, is_primary_key=True, ordinal_position=1),
        _field("field_id", ordinal_position=2),
        _field("nominal_species_id", ordinal_position=3),
        _field("common_name", ordinal_position=4),
        _field("collector", ordinal_position=5),
        _field("contact", ordinal_position=6),
        _field("date_collected", data_type="date", postgres_type="date", ordinal_position=7),
        _field("sex", ordinal_position=8),
        _field("weight", ordinal_position=9),
        _field("lengthtl_and_lengthfl", ordinal_position=10),
        _field("country", ordinal_position=11),
        _field("state", ordinal_position=12),
        _field("location", ordinal_position=13),
        _field("latitude_collection", ordinal_position=14),
        _field("longitude_collection", ordinal_position=15),
        _field("depth_collection", ordinal_position=16),
        _field("collection_method", ordinal_position=17),
        _field("preservation_method", ordinal_position=18),
        _field("sample_condition", ordinal_position=19),
        _field("photo_voucher", ordinal_position=20),
        _field("photo_id", ordinal_position=21),
        _field("specimen_voucher", ordinal_position=22),
        _field("voucher_id", ordinal_position=23),
        _field("comments", ordinal_position=24),
        _field("priority", ordinal_position=25),
        _field("tissues", ordinal_position=26),
        _field("extracted", ordinal_position=27),
        _field("extraction_queue", ordinal_position=28),
        _field("ilmn", ordinal_position=29),
        _field("il_status", ordinal_position=30),
        _field("hifi", ordinal_position=31),
        _field("pb_status", ordinal_position=32),
        _field("hic", ordinal_position=33),
        _field("hic_status", ordinal_position=34),
        _field("nano", ordinal_position=35),
        _field("ont_num", ordinal_position=36),
        _field("rna", ordinal_position=37),
        _field("rna_status", ordinal_position=38),
        _field("ilrna", ordinal_position=39),
        _field("ilrna_status", ordinal_position=40),
        _field("assigned_species", ordinal_position=41),
        _field("og_num", data_type="integer", postgres_type="int4", ordinal_position=42),
        _field("project_id", ordinal_position=43),
        _field("workflow", data_type="character varying", postgres_type="varchar", ordinal_position=44),
        _field("summary_comments", data_type="character varying", postgres_type="varchar", ordinal_position=45),
        _field("embargo_status", data_type="character varying", postgres_type="varchar", ordinal_position=46),
    ]


def _write_schema_csv(path: Path):
    rows = [
        {
            "table_schema": "public",
            "table_name": "sample",
            "primary_key_columns": json.dumps(["og_id"]),
            "unique_constraints": json.dumps([]),
            "foreign_keys": json.dumps([]),
            "fields": json.dumps(_sample_fields()),
        },
        {
            "table_schema": "public",
            "table_name": "tissue",
            "primary_key_columns": json.dumps(["tissue_id"]),
            "unique_constraints": json.dumps([]),
            "foreign_keys": json.dumps(
                [
                    {
                        "constraint_name": "fk_og_id",
                        "columns": ["og_id"],
                        "references": {
                            "schema": "public",
                            "table": "sample",
                            "columns": ["og_id"],
                        },
                    }
                ]
            ),
            "fields": json.dumps(
                [
                    _field("tissue_id", is_nullable=False, is_primary_key=True, ordinal_position=1),
                    _field("og_id", ordinal_position=2),
                    _field("tissue", ordinal_position=3),
                ]
            ),
        },
        {
            "table_schema": "public",
            "table_name": "sample_view",
            "primary_key_columns": json.dumps([]),
            "unique_constraints": json.dumps([]),
            "foreign_keys": json.dumps([]),
            "fields": json.dumps(
                [
                    _field("og_id_sv", ordinal_position=1),
                    _field("proj_id", ordinal_position=2),
                ]
            ),
        },
        {
            "table_schema": "public",
            "table_name": "rna_extraction",
            "primary_key_columns": json.dumps(["rna_id"]),
            "unique_constraints": json.dumps([]),
            "foreign_keys": json.dumps(
                [
                    {
                        "constraint_name": "fk_rna_og_id",
                        "columns": ["og_id"],
                        "references": {
                            "schema": "public",
                            "table": "sample",
                            "columns": ["og_id"],
                        },
                    },
                    {
                        "constraint_name": "fk_rna_tissue_id",
                        "columns": ["tissue_id"],
                        "references": {
                            "schema": "public",
                            "table": "tissue",
                            "columns": ["tissue_id"],
                        },
                    },
                ]
            ),
            "fields": json.dumps(
                [
                    _field("rna_id", is_nullable=False, is_primary_key=True, ordinal_position=1),
                    _field("og_id", ordinal_position=2),
                    _field("tissue_id", ordinal_position=3),
                    _field("ext_num", data_type="integer", postgres_type="int4", ordinal_position=4),
                    _field("status", ordinal_position=5),
                    _field("extraction_method", ordinal_position=6),
                    _field("extraction_date", data_type="date", postgres_type="date", ordinal_position=7),
                    _field("extraction_batch_id", ordinal_position=8),
                    _field("final_buffer", ordinal_position=9),
                    _field("volume", data_type="integer", postgres_type="int4", ordinal_position=10),
                    _field("qubit_conc", data_type="real", postgres_type="float4", ordinal_position=11),
                    _field("nano_drop_conc", data_type="real", postgres_type="float4", ordinal_position=12),
                    _field("ratio_260_280", ordinal_position=13),
                    _field("ratio_260_230", ordinal_position=14),
                    _field("total_yield", data_type="integer", postgres_type="int4", ordinal_position=15),
                    _field("tapestation_id", ordinal_position=16),
                    _field("rna_dv200", data_type="real", postgres_type="float4", ordinal_position=17),
                    _field("rin", ordinal_position=18),
                    _field("extraction_qc", ordinal_position=19),
                    _field("comment", ordinal_position=20),
                    _field("rna_freezer", ordinal_position=21),
                    _field("rna_shelf", ordinal_position=22),
                    _field("rna_rack", ordinal_position=23),
                    _field("rna_level", ordinal_position=24),
                    _field("rna_box", ordinal_position=25),
                    _field("rna_notes", ordinal_position=26),
                    _field("status_overwrite", data_type="character varying", postgres_type="varchar", ordinal_position=27),
                ]
            ),
        },
    ]

    with path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "table_schema",
                "table_name",
                "primary_key_columns",
                "unique_constraints",
                "foreign_keys",
                "fields",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


class SchemaMetadataTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.metadata_path = Path(cls.temp_dir.name) / "schema.csv"
        _write_schema_csv(cls.metadata_path)
        cls.settings_override = override_settings(
            SCHEMA_METADATA_PATH=str(cls.metadata_path),
            DATA_EXPLORER_DATABASE_ALIAS="default",
        )
        cls.settings_override.enable()
        load_schema_catalog.cache_clear()

    @classmethod
    def tearDownClass(cls):
        load_schema_catalog.cache_clear()
        cls.settings_override.disable()
        cls.temp_dir.cleanup()
        super().tearDownClass()


class SavedTableViewBehaviorTests(SchemaMetadataTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="password123")

    def test_first_saved_view_for_table_becomes_default(self):
        saved_view = SavedTableView.objects.create(
            user=self.user,
            table_name="sample",
            name="Core Sample Columns",
            visible_columns=["og_id", "common_name"],
            ordering="og_id",
            is_default=False,
        )

        self.assertTrue(saved_view.is_default)

    def test_new_default_only_replaces_default_on_same_table(self):
        first = SavedTableView.objects.create(
            user=self.user,
            table_name="sample",
            name="Primary",
            visible_columns=["og_id", "common_name"],
            ordering="og_id",
            is_default=True,
        )
        SavedTableView.objects.create(
            user=self.user,
            table_name="tissue",
            name="Tissue Layout",
            visible_columns=["tissue_id", "og_id"],
            ordering="tissue_id",
            is_default=True,
        )
        second = SavedTableView.objects.create(
            user=self.user,
            table_name="sample",
            name="Secondary",
            visible_columns=["og_id", "collector"],
            ordering="-og_id",
            is_default=True,
        )

        first.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)
        self.assertTrue(
            SavedTableView.objects.get(user=self.user, table_name="tissue", name="Tissue Layout").is_default
        )


class ExplorerViewTests(SchemaMetadataTestCase):
    @classmethod
    def setUpTestData(cls):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS rna_extraction")
            cursor.execute("DROP TABLE IF EXISTS tissue")
            cursor.execute("DROP TABLE IF EXISTS sample")
            cursor.execute(
                """
                CREATE TABLE sample (
                    og_id TEXT PRIMARY KEY,
                    field_id TEXT,
                    nominal_species_id TEXT,
                    common_name TEXT,
                    collector TEXT,
                    contact TEXT,
                    date_collected DATE,
                    sex TEXT,
                    weight TEXT,
                    lengthtl_and_lengthfl TEXT,
                    country TEXT,
                    state TEXT,
                    location TEXT,
                    latitude_collection TEXT,
                    longitude_collection TEXT,
                    depth_collection TEXT,
                    collection_method TEXT,
                    preservation_method TEXT,
                    sample_condition TEXT,
                    photo_voucher TEXT,
                    photo_id TEXT,
                    specimen_voucher TEXT,
                    voucher_id TEXT,
                    comments TEXT,
                    priority TEXT,
                    tissues TEXT,
                    extracted TEXT,
                    extraction_queue TEXT,
                    ilmn TEXT,
                    il_status TEXT,
                    hifi TEXT,
                    pb_status TEXT,
                    hic TEXT,
                    hic_status TEXT,
                    nano TEXT,
                    ont_num TEXT,
                    rna TEXT,
                    rna_status TEXT,
                    ilrna TEXT,
                    ilrna_status TEXT,
                    assigned_species TEXT,
                    og_num INTEGER,
                    project_id TEXT,
                    workflow TEXT,
                    summary_comments TEXT,
                    embargo_status TEXT
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO sample (
                    og_id,
                    field_id,
                    nominal_species_id,
                    common_name,
                    collector,
                    date_collected,
                    location,
                    sample_condition,
                    og_num,
                    project_id,
                    priority,
                    workflow,
                    tissues,
                    extracted,
                    ilmn,
                    il_status,
                    hifi,
                    pb_status,
                    hic,
                    hic_status,
                    nano,
                    ont_num,
                    rna,
                    rna_status
                )
                VALUES
                    ('OG-001', 'F-001', 'Prionace glauca', 'Blue Shark', 'J. Smith', DATE '2023-05-01', 'Perth', 'Frozen', 1, 'OGP001', 'Immediate', 'Reference', '2', '1', 'Y', 'Queued', 'Y', 'Queued', 'N', 'Not Started', 'N', '0', 'N', 'Not Started'),
                    ('OG-002', 'F-002', 'Isurus oxyrinchus', 'Mako Shark', 'A. Jones', DATE '2023-06-01', 'Albany', 'Fresh', 2, 'OGP002', 'Routine', 'Reference', '1', '1', 'N', 'Not Started', 'N', 'Not Started', 'N', 'Not Started', 'N', '0', 'N', 'Not Started')
                """
            )
            cursor.execute(
                """
                CREATE TABLE tissue (
                    tissue_id TEXT PRIMARY KEY,
                    og_id TEXT,
                    tissue TEXT,
                    box TEXT
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO tissue (tissue_id, og_id, tissue, box)
                VALUES ('OG1G', 'OG-001', 'Gills', 'TIS-BOX-01')
                """
            )
            cursor.execute(
                """
                CREATE TABLE rna_extraction (
                    rna_id TEXT PRIMARY KEY,
                    og_id TEXT,
                    tissue_id TEXT,
                    ext_num INTEGER,
                    status TEXT,
                    extraction_method TEXT,
                    extraction_date DATE,
                    extraction_batch_id TEXT,
                    final_buffer TEXT,
                    volume INTEGER,
                    qubit_conc REAL,
                    nano_drop_conc REAL,
                    ratio_260_280 TEXT,
                    ratio_260_230 TEXT,
                    total_yield INTEGER,
                    tapestation_id TEXT,
                    rna_dv200 REAL,
                    rin TEXT,
                    extraction_qc TEXT,
                    comment TEXT,
                    rna_freezer TEXT,
                    rna_shelf TEXT,
                    rna_rack TEXT,
                    rna_level TEXT,
                    rna_box TEXT,
                    rna_notes TEXT,
                    status_overwrite TEXT
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO rna_extraction (
                    rna_id,
                    og_id,
                    tissue_id,
                    ext_num,
                    status,
                    extraction_method,
                    extraction_date,
                    extraction_batch_id,
                    final_buffer,
                    volume,
                    qubit_conc,
                    nano_drop_conc,
                    ratio_260_280,
                    ratio_260_230,
                    total_yield,
                    tapestation_id,
                    rna_dv200,
                    rin,
                    extraction_qc,
                    comment,
                    rna_freezer,
                    rna_shelf,
                    rna_rack,
                    rna_level,
                    rna_box,
                    rna_notes,
                    status_overwrite
                )
                VALUES (
                    'OG1G_R',
                    'OG-001',
                    'OG1G',
                    1,
                    'Queued',
                    'Trizol',
                    DATE '2024-02-10',
                    'RNA_RNEASY_240210_LA',
                    'Nuclease-free water',
                    100,
                    17.2,
                    21.4,
                    '2.05',
                    '1.71',
                    1720,
                    'TS_RNA_240211_LA',
                    84.77,
                    '4.9',
                    'MAYBE',
                    'Initial extraction',
                    'Archive-A',
                    '4',
                    '1',
                    'A',
                    'RNA-BOX-01',
                    'Lab note',
                    ''
                )
                """
            )

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="explorer", password="password123")
        self.client.force_login(self.user)

    def test_dashboard_uses_schema_export(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Schema dashboard")
        self.assertContains(response, "sample")
        self.assertContains(response, "sample_view")
        self.assertContains(response, "Specimen Intake")
        self.assertContains(response, "Tissue Inventory")

    def test_table_catalog_lists_schema_relations(self):
        response = self.client.get("/tables/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sample")
        self.assertContains(response, "tissue")
        self.assertContains(response, "sample_view")
        self.assertContains(response, "Specimen Intake")
        self.assertContains(response, "Sequencing Readiness")

    def test_table_detail_renders_live_rows_and_search(self):
        response = self.client.get("/tables/sample/?q=blue")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blue Shark")
        self.assertNotContains(response, "Mako Shark")

    def test_table_detail_can_activate_lab_preset(self):
        response = self.client.get("/tables/sample/?preset=specimen-intake")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Specimen Intake")
        self.assertContains(response, "Core specimen identity, collection, and operational intake fields.")

    def test_row_detail_uses_primary_key_from_metadata(self):
        response = self.client.get("/tables/sample/row/?og_id=OG-002")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mako Shark")
        self.assertContains(response, "A. Jones")

    def test_saved_view_page_lists_shared_lab_presets(self):
        response = self.client.get("/views/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lab workflow presets")
        self.assertContains(response, "Specimen Intake")
        self.assertContains(response, "Saved joined views")

    def test_metadata_worksheet_lists_existing_rows(self):
        response = self.client.get("/worksheets/metadata/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1.MetaData")
        self.assertContains(response, "Blue Shark")
        self.assertContains(response, "Mako Shark")

    def test_metadata_worksheet_can_create_row(self):
        response = self.client.post(
            "/worksheets/metadata/new/",
            {
                "project_id": "OGP003",
                "field_id": "F-003",
                "nominal_species_id": "Carcharhinus obscurus",
                "common_name": "Dusky Shark",
                "collector": "L. Brown",
                "contact": "lab@example.com",
                "date_collected": "2024-01-15",
                "sex": "F",
                "weight": "1200",
                "lengthtl_and_lengthfl": "1800",
                "country": "Australia",
                "state": "WA",
                "location": "Broome",
                "latitude_collection": "-17.961",
                "longitude_collection": "122.236",
                "depth_collection": "35",
                "collection_method": "Net",
                "preservation_method": "Frozen",
                "sample_condition": "Good",
                "photo_voucher": "Yes",
                "photo_id": "PHOTO-001",
                "specimen_voucher": "No",
                "voucher_id": "",
                "comments": "New intake row",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Created specimen")
        with connection.cursor() as cursor:
            cursor.execute("SELECT og_num, og_id, common_name FROM sample WHERE common_name = 'Dusky Shark'")
            self.assertEqual(cursor.fetchone(), (3, "OG3", "Dusky Shark"))

    def test_metadata_worksheet_can_edit_row(self):
        response = self.client.post(
            "/worksheets/metadata/OG-001/edit/",
            {
                "project_id": "OGP001",
                "field_id": "F-001",
                "nominal_species_id": "Prionace glauca",
                "common_name": "Blue Shark Updated",
                "collector": "J. Smith",
                "contact": "",
                "date_collected": "2023-05-01",
                "sex": "",
                "weight": "",
                "lengthtl_and_lengthfl": "",
                "country": "",
                "state": "",
                "location": "Perth",
                "latitude_collection": "",
                "longitude_collection": "",
                "depth_collection": "",
                "collection_method": "",
                "preservation_method": "",
                "sample_condition": "Frozen",
                "photo_voucher": "",
                "photo_id": "",
                "specimen_voucher": "",
                "voucher_id": "",
                "comments": "Updated",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Updated specimen OG-001.")
        with connection.cursor() as cursor:
            cursor.execute("SELECT common_name, comments FROM sample WHERE og_id = 'OG-001'")
            self.assertEqual(cursor.fetchone(), ("Blue Shark Updated", "Updated"))

    def test_metadata_worksheet_bulk_update_endpoint(self):
        response = self.client.post(
            "/worksheets/metadata/bulk-update/",
            data=json.dumps(
                {
                    "rows": [
                        {
                            "id": "OG-001",
                            "changes": {
                                "common_name": "Blue Shark Bulk",
                                "collector": "Bulk Editor",
                            },
                        }
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"ok": True, "updated_count": 1})
        with connection.cursor() as cursor:
            cursor.execute("SELECT common_name, collector FROM sample WHERE og_id = 'OG-001'")
            self.assertEqual(cursor.fetchone(), ("Blue Shark Bulk", "Bulk Editor"))

    def test_joined_view_builder_shows_related_parent_columns(self):
        response = self.client.get("/joined-views/new/?base_table=rna_extraction")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "rna_extraction.status")
        self.assertContains(response, "sample.common_name")
        self.assertContains(response, "tissue.tissue")

    def test_joined_view_can_create_and_render_combined_rows(self):
        response = self.client.post(
            "/joined-views/new/",
            {
                "name": "RNA worksheet",
                "base_table_name": "rna_extraction",
                "visible_columns": [
                    "rna_extraction.rna_id",
                    "rna_extraction.status",
                    "sample.common_name",
                    "tissue.tissue",
                ],
                "ordering": "rna_extraction.rna_id",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Joined view created.")
        self.assertContains(response, "RNA worksheet")
        self.assertContains(response, "OG1G_R")
        self.assertContains(response, "Blue Shark")
        self.assertContains(response, "Gills")

        saved_view = SavedJoinedView.objects.get(user=self.user, name="RNA worksheet")
        self.assertEqual(saved_view.base_table_name, "rna_extraction")

    def test_rna_worksheet_lists_existing_rows(self):
        response = self.client.get("/worksheets/rna-extractions/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "3.RNAExtractions")
        self.assertContains(response, "OG1G_R")
        self.assertContains(response, "Blue Shark")

    def test_rna_worksheet_can_create_row(self):
        response = self.client.post(
            "/worksheets/rna-extractions/new/",
            {
                "tissue_id": "OG1G",
                "ext_num": 2,
                "status": "Extracted",
                "extraction_method": "Qiagen RNeasy Plus",
                "extraction_date": "2024-03-01",
                "extraction_batch_id": "RNA_BATCH_240301",
                "final_buffer": "Nuclease-free water",
                "volume": 80,
                "qubit_conc": 18.6,
                "nano_drop_conc": 22.1,
                "ratio_260_280": "2.02",
                "ratio_260_230": "1.80",
                "total_yield": 1488,
                "tapestation_id": "TS_RNA_240301",
                "rna_dv200": 91.2,
                "rin": "8.4",
                "extraction_qc": "PASS",
                "status_overwrite": "",
                "comment": "Repeat extraction",
                "rna_freezer": "Archive-B",
                "rna_shelf": "5",
                "rna_rack": "2",
                "rna_level": "B",
                "rna_box": "RNA-BOX-02",
                "rna_notes": "Stored and ready",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Created RNA extraction OG1G_R2")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rna_id, og_id, tissue_id, ext_num, extraction_qc FROM rna_extraction WHERE rna_id = 'OG1G_R2'"
            )
            self.assertEqual(cursor.fetchone(), ("OG1G_R2", "OG-001", "OG1G", 2, "PASS"))

    def test_rna_worksheet_can_edit_row(self):
        response = self.client.post(
            "/worksheets/rna-extractions/OG1G_R/edit/",
            {
                "tissue_id": "OG1G",
                "ext_num": 1,
                "status": "Archived",
                "extraction_method": "Trizol",
                "extraction_date": "2024-02-10",
                "extraction_batch_id": "RNA_RNEASY_240210_LA",
                "final_buffer": "Nuclease-free water",
                "volume": 100,
                "qubit_conc": 17.2,
                "nano_drop_conc": 21.4,
                "ratio_260_280": "2.05",
                "ratio_260_230": "1.71",
                "total_yield": 1720,
                "tapestation_id": "TS_RNA_240211_LA",
                "rna_dv200": 84.77,
                "rin": "4.9",
                "extraction_qc": "PASS",
                "status_overwrite": "Override",
                "comment": "Updated note",
                "rna_freezer": "Archive-A",
                "rna_shelf": "4",
                "rna_rack": "1",
                "rna_level": "A",
                "rna_box": "RNA-BOX-01",
                "rna_notes": "Moved to archive",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Updated RNA extraction OG1G_R.")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, extraction_qc, status_overwrite, comment, rna_notes FROM rna_extraction WHERE rna_id = 'OG1G_R'"
            )
            self.assertEqual(cursor.fetchone(), ("Archived", "PASS", "Override", "Updated note", "Moved to archive"))

    def test_rna_worksheet_bulk_update_endpoint(self):
        response = self.client.post(
            "/worksheets/rna-extractions/bulk-update/",
            data=json.dumps(
                {
                    "rows": [
                        {
                            "id": "OG1G_R",
                            "changes": {
                                "status": "Completed",
                                "extraction_qc": "PASS",
                                "status_overwrite": "Reviewed",
                            },
                        }
                    ]
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"ok": True, "updated_count": 1})
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, extraction_qc, status_overwrite FROM rna_extraction WHERE rna_id = 'OG1G_R'"
            )
            self.assertEqual(cursor.fetchone(), ("Completed", "PASS", "Reviewed"))
