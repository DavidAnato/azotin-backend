# AZƆBATIN

## Lancer le projet django

1. Se rendre dans le dossier `azobatin_api`
2. Creer un environnement virtuel et installer les dépendances avec
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
3. Faire la migration des models avec
```bash
python manage.py migrate
```
4. Lancer le serveur avec
```bash
python manage.py runserver 0.0.0.0:8000
```

## Seed (automatique)

Le dashboard Render peut appeler `python seeddata.py` après `collectstatic`,
et l’entrypoint lance aussi `manage.py seeddata` au démarrage.

Désactiver : `SKIP_SEED=1`

Manuel :

```bash
python manage.py seeddata
python manage.py seeddata --reset
python seeddata.py --reset
```
