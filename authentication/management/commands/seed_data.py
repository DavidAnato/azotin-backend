from django.core.management.base import BaseCommand

from seed_data import seed_data


class Command(BaseCommand):
    help = "Charge les données de démonstration (voir seed_data.py)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Supprime les données métier avant de regénérer.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            import os

            os.environ["SEED_RESET"] = "1"
        seed_data()
        self.stdout.write(self.style.SUCCESS("Seed terminé."))
