#!/usr/bin/env python
"""
Compatibilité Build Command Render : `python seeddata.py`.

Le dashboard Render appelle encore ce fichier après collectstatic.
Le seed en **build** prod est dangereux (DB mutée à chaque deploy, échec
si la base n'est pas prête). Par défaut ce script ne fait rien (exit 0)
pour que le build réussisse.

Pour charger les données (local ou Shell Render one-off) :
  python manage.py seeddata
  python manage.py seeddata --reset
  RUN_SEED=1 python seeddata.py
  python seeddata.py --reset

Variables d'environnement (quand le seed est réellement lancé) :
  RUN_SEED=1
  SEED_RESET=1
  SEED_SKIP_NETWORK=1
  SEED_SUPERUSER_PHONE / SEED_SUPERUSER_PASSWORD
"""

from __future__ import annotations

import argparse
import os
import sys


def _should_run_seed(reset: bool) -> bool:
    if reset:
        return True
    return os.environ.get("RUN_SEED", "0") == "1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed données de démonstration AZOTIN.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Supprime les données métier avant de regénérer (force le seed).",
    )
    args = parser.parse_args(argv)

    if not _should_run_seed(args.reset):
        print(
            "seed skipped; run manually: python manage.py seeddata "
            "(or RUN_SEED=1 python seeddata.py / python seeddata.py --reset)",
            file=sys.stderr,
        )
        return 0

    if args.reset:
        os.environ["SEED_RESET"] = "1"

    # Importe après éventuel SEED_RESET (seed_data lit l'env au runtime).
    from seed_data import seed_data

    seed_data()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
