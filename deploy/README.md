# Déploiement AZƆBATIN API sur un VPS Linux

## Prérequis

- Docker Engine et le plugin Docker Compose
- Un nom DNS pointant vers le VPS et un reverse proxy TLS (Nginx, Caddy ou Traefik)
- Des identifiants SMTP, GetOurVoice et FedaPay de production

Le service Django écoute uniquement sur `127.0.0.1:8000`. PostgreSQL et Redis ne publient aucun port vers Internet. Les médias et la base sont conservés dans des volumes Docker.

## Configuration

Depuis la racine du dépôt :

```bash
cp .env.example .env
chmod 600 .env
```

Édite `.env` : remplace toutes les valeurs `CHANGE_ME`, vérifie les domaines, et ajoute les vrais secrets. Génère les secrets avec un gestionnaire sûr, par exemple `openssl rand -hex 64` pour `SECRET_KEY` et un mot de passe PostgreSQL aléatoire dédié. Ne mets jamais `.env` dans Git.

`FEDAPAY_ENVIRONMENT=live` exige les trois clés live. Le service refuse de démarrer si la clé Django est faible, si `DEBUG` ou le bypass OTP est activé, si les origines ne sont pas en HTTPS, ou si les paramètres DB/Redis/SMTP/FedaPay requis manquent.

## Démarrage / mise à jour

```bash
docker compose --env-file .env -f deploy/docker-compose.yml config --quiet
docker compose --env-file .env -f deploy/docker-compose.yml up -d --build
docker compose --env-file .env -f deploy/docker-compose.yml ps
```

L’entrypoint applique les migrations et collecte les assets statiques avant de démarrer Uvicorn/ASGI. Les WebSockets et le streaming de notifications passent par ce serveur. Configure le reverse proxy pour transférer `Host`, `X-Forwarded-Proto: https`, `X-Forwarded-For`, et les en-têtes `Upgrade` / `Connection` vers `127.0.0.1:8000`. Augmente la taille maximale des corps de requête pour les images KYC.

Le service n’expose pas `/media` via Django en production. Les documents sont conservés dans le volume `media_data`; configure un accès privé côté administration si les opérateurs doivent consulter les pièces KYC.

## Première administration

Après le premier démarrage, crée le compte admin explicitement :

```bash
docker compose --env-file .env -f deploy/docker-compose.yml exec api python manage.py createsuperuser
```

Il n’existe aucun compte admin ou données de démonstration intégrés au démarrage.

## Sauvegardes

Sauvegarde PostgreSQL et le volume médias de manière cohérente et stocke les sauvegardes hors du VPS. Avant une mise à jour, fais une sauvegarde ; les migrations sont exécutées automatiquement au démarrage du conteneur.

```bash
docker compose --env-file .env -f deploy/docker-compose.yml exec -T db \
  pg_dump -U "$DB_USER" "$DB_NAME" > "backup-$(date +%F).sql"
```

Teste régulièrement la restauration des sauvegardes.
