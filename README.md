# AZƆBATIN API

## Développement local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Sous Linux/macOS, active `.venv/bin/activate`. La configuration de développement est sélectionnée par `manage.py`.

## Déploiement sur VPS

Lire [`deploy/README.md`](deploy/README.md). PostgreSQL, Redis, ASGI/WebSockets et les fichiers médias sont persistés avec Docker Compose. Le service ne crée aucun compte ni jeu de données par défaut ; créer le premier administrateur avec la commande Django `createsuperuser`.

## Qualité

GitHub Actions lance les tests Django, `check`, la détection de migrations, Flake8, Black, isort et mypy sur `main`, `develop` et les pull requests.
