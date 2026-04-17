# CimentApp — Guide A→Z (Docker)

Ce dépôt contient une application **Django + MySQL** (module utilisateurs + module articles).
Ce README explique comment **cloner, configurer, lancer, migrer, dépanner** le projet **avec Docker**.

---

## Pré-requis

- **Docker Desktop** (Windows/macOS/Linux)
- **Docker Compose v2** (inclus dans Docker Desktop)
- Un terminal (PowerShell recommandé sur Windows)

Vérifier :

```bash
docker --version
docker compose version
```

---

## 1) Première installation (une fois)

### 1.1 Cloner le projet

```bash
git clone <repo>
cd cimentapp
```

### 1.2 Créer le fichier `.env`

Le projet utilise un `.env` (non versionné). Copiez le modèle :

```bash
cp .env.example .env
```

Sur Windows PowerShell :

```powershell
Copy-Item .env.example .env
```

Ensuite éditez `.env` et remplacez **tous** les `change-me`.

Fichier attendu (extrait) :

- `DEBUG=True` en dev
- `SECRET_KEY=...` (valeur longue)
- `ALLOWED_HOSTS=127.0.0.1,localhost` (ajoutez votre IP LAN si besoin)
- `DB_*` : utilisés par Django **dans le conteneur**
- `MYSQL_ROOT_PASSWORD` : utilisé par le conteneur MySQL

---

## 2) Lancer l’application (Docker)

### 2.1 Démarrer les conteneurs

```bash
docker compose up --build
```

Ce que fait le démarrage :

- démarre MySQL (service `db`)
- démarre Django (service `web`)
- **attend MySQL** puis exécute automatiquement :
  - `python manage.py migrate`
  - `python manage.py runserver 0.0.0.0:8000`

L’app est accessible sur :

- `http://localhost:8000/`

### 2.2 Démarrer en arrière-plan (optionnel)

```bash
docker compose up -d --build
docker compose logs -f web
```

### 2.3 Arrêter

```bash
docker compose down
```

### 2.4 Réinitialiser la base (attention : perte de données)

La base MySQL est persistée dans un volume Docker `mysql_data`.
Pour tout supprimer :

```bash
docker compose down -v
```

---

## 3) Commandes utiles (dans Docker)

### 3.1 Ouvrir un shell dans le conteneur web

```bash
docker compose exec web bash
```

### 3.2 Commandes Django

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py shell
```

### 3.3 Accéder à MySQL

Le port MySQL est exposé côté host sur **3307** (voir `docker-compose.yml`).
Depuis votre machine :

- hôte : `127.0.0.1`
- port : `3307`
- user/pass/db : ceux de `.env`

Depuis un client dans Docker :

```bash
docker compose exec db mysql -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME"
```

---

## 4) Structure des services Docker (explication)

### `docker-compose.yml`

- **web** : Django
  - monte le code en volume `.:/cimentapp` (hot reload)
  - expose `8000:8000`
  - charge `.env`
- **db** : MySQL 8
  - expose `3307:3306`
  - volume persistant `mysql_data`
  - healthcheck `mysqladmin ping`

### `Dockerfile`

- image `python:3.12-slim`
- installe dépendances système MySQL (`default-libmysqlclient-dev`, `gcc`, etc.)
- installe les dépendances Python via `requirements.txt`
- utilise `entrypoint.sh`

### `entrypoint.sh`

1) attend que MySQL réponde sur `$DB_HOST:$DB_PORT`
2) exécute `python manage.py migrate`
3) lance `python manage.py runserver 0.0.0.0:8000`

---

## 5) Problèmes courants & solutions (Troubleshooting)

### A) “Site inaccessible” depuis un autre appareil (téléphone, autre PC)

1) Lancez le serveur via Docker (déjà en `0.0.0.0:8000`)
2) Trouvez l’IP LAN de votre PC (Windows) :

```powershell
ipconfig
```

3) Ajoutez l’IP dans `.env` :

Exemple :

```env
ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.228
```

4) Ouvrez depuis le téléphone :

- `http://192.168.1.228:8000/`

5) Pare-feu Windows :
- autoriser Docker / Python / port **8000** sur **réseau privé**

### B) Django affiche `DisallowedHost`

Cause : `ALLOWED_HOSTS` ne contient pas l’host utilisé.

Solution : ajouter l’IP/hostname dans `.env` puis redémarrer :

```bash
docker compose restart web
```

### C) Le conteneur `web` boucle sur “Waiting for MySQL…”

Causes typiques :
- mauvais `DB_HOST` / `DB_PORT` dans `.env`
- MySQL n’arrive pas à démarrer (mot de passe root invalide, volume corrompu)

Vérifier :

```bash
docker compose logs -f db
```

Solutions :
- corriger `.env` (`DB_HOST=db`, `DB_PORT=3306`)
- si vous pouvez perdre la base : `docker compose down -v` puis `docker compose up --build`

### D) Erreur MySQL “Access denied”

Cause : mauvais `DB_USER` / `DB_PASSWORD` / `DB_NAME`.

Solutions :
- vérifiez `.env`
- si la base a été initialisée avec d’anciennes valeurs, recréez le volume :
  - `docker compose down -v`
  - `docker compose up --build`

### E) “Can’t connect to MySQL server”

Depuis le host : utilisez **3307** (pas 3306) car compose mappe `3307:3306`.

### F) Les migrations échouent au démarrage

Le `entrypoint.sh` lance `migrate` automatiquement.
Pour voir l’erreur :

```bash
docker compose logs -f web
```

Actions fréquentes :
- régénérer migrations si besoin : `docker compose exec web python manage.py makemigrations`
- relancer : `docker compose restart web`

### G) Les fichiers media (images) ne s’affichent pas

En `DEBUG=True`, Django sert `MEDIA_URL` via `config/urls.py`.

À vérifier :
- `.env` contient `DEBUG=True`
- `config/urls.py` contient bien le bloc `if settings.DEBUG: ... static(...)`

Note : le dossier `media/` est ignoré par git (`.gitignore`).

---

## 6) Workflow dev recommandé (équipe)

### Démarrage quotidien

```bash
docker compose up
```

### Après un pull (si nouvelles migrations)

Le conteneur exécute déjà `migrate`, mais si vous êtes en `-d` :

```bash
docker compose exec web python manage.py migrate
```

### Ajouter une dépendance Python

1) Ajouter dans `requirements.txt`
2) rebuild :

```bash
docker compose build web
docker compose up -d
```

---

## 7) Notes sécurité (dev)

- Ne commitez jamais `.env`
- Remplacez `SECRET_KEY` et mots de passe par des valeurs fortes
- En prod : `DEBUG=False` + gestion d’un serveur (gunicorn/uwsgi) + reverse proxy (Nginx) + TLS

---

## 8) FAQ rapide

### “Je veux repartir de zéro”

```bash
docker compose down -v
docker compose up --build
```

### “Je veux juste relancer Django”

```bash
docker compose restart web
```

