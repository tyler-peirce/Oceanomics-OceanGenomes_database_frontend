from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from portal.models import SavedTableView
from portal.schema import SchemaMetadataError, get_schema_catalog


class Command(BaseCommand):
    help = "Create a demo user and a few saved table layouts for the Oceanomics explorer."

    def handle(self, *args, **options):
        user_model = get_user_model()
        analyst, _ = user_model.objects.get_or_create(
            username="oceanomics_analyst",
            defaults={"email": "oceanomics_analyst@example.com"},
        )
        analyst.set_password("ChangeMe123!")
        analyst.save()

        try:
            catalog = {table.name: table for table in get_schema_catalog()}
        except SchemaMetadataError as exc:
            raise RuntimeError(str(exc)) from exc

        default_tables = ("sample", "tissue", "sequencing")
        created = 0
        for table_name in default_tables:
            table = catalog.get(table_name)
            if table is None:
                continue

            SavedTableView.objects.update_or_create(
                user=analyst,
                table_name=table_name,
                name=f"{table.label} Default",
                defaults={
                    "visible_columns": table.default_visible_columns,
                    "ordering": table.default_ordering,
                    "is_default": True,
                },
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo explorer assets loaded. User: oceanomics_analyst / password: ChangeMe123! "
                f"Saved views created: {created}"
            )
        )
