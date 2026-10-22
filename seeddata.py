#!/usr/bin/env python
"""
Compatibilité Build Command Render : `python seeddata.py`.

Seed automatique par défaut (build / start Render).
Pour désactiver : SKIP_SEED=1

  python manage.py seeddata
  python manage.py seeddata --reset
  python seeddata.py --reset
  SKIP_SEED=1 python seeddata.py

Variables d'environnement :
  SKIP_SEED=1
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
    # Opt-out : SKIP_SEED=1 désactive le seed auto
    return os.environ.get("SKIP_SEED", "0") != "1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed données de démonstration AZOBATIN.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Supprime les données métier avant de regénérer (force le seed).",
    )
    args = parser.parse_args(argv)

    if not _should_run_seed(args.reset):
        print(
            "seed skipped (SKIP_SEED=1); run manually: python manage.py seeddata",
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
