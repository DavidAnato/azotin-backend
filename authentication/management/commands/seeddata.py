"""Alias de la commande seed_data.

Usage :
  python manage.py seeddata
  python manage.py seeddata --reset
"""

from .seed_data import Command as SeedDataCommand


class Command(SeedDataCommand):
    help = "Alias de seed_data — charge les données de démonstration."
