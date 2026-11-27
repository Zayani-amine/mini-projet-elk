# Mini-Projet ELK — Monitoring et analyse de logs (Smart Building IoT)

IT Business School — Zayani Mohamed Amine — Encadrant : Mohamed Najeh ISSAOUI

[![CI](https://github.com/Zayani-amine/mini-projet-elk/actions/workflows/ci.yml/badge.svg)](https://github.com/Zayani-amine/mini-projet-elk/actions/workflows/ci.yml)

Objectif 20/20 : socle (modules 1 à 5) + module L (observabilité) + module K (CI/CD et tests).

Scénario B : plateforme de centralisation, d'indexation et d'analyse des logs d'un bâtiment intelligent (~300 capteurs, 5 types de logs).

Stack : Elasticsearch / Logstash / Kibana 8.x, MongoDB 7, Redis 7, Flask 3, Docker Compose 2, Bootstrap 5, Chart.js.

## Numérotation

La numérotation **Jira** est la référence : `ELK-7` à `ELK-36` avec les identifiants `[T01]` à `[T30]`.
Les PDF de sprint 1 utilisent un décalage de -6 (leur `ELK-7` correspond à `ELK-13`). Les commits suivent le format `ELK-xx [Txx] description`.

## État d'avancement

| Sprint | Semaines | Tickets Jira | État |
| --- | --- | --- | --- |
| 1 | S1-S2 | ELK-7 à ELK-12 `[T01]`-`[T06]` | Terminé (analyse, architecture, mapping, maquettes, revue n°1) |
| 2 | S3-S4 | ELK-13 à ELK-18 `[T07]`-`[T12]` | Terminé (socle, Faker, templates, CI GitHub Actions) |
| 3 | S5-S6 | ELK-19 à ELK-24 `[T13]`-`[T18]` | Terminé (upload, ingestion, recherche, API) |
| 4 | S7-S8 | ELK-25 à ELK-31 `[T19]`-`[T25]` | Terminé (frontend Bootstrap 5, KPIs, export CSV, cache Redis, Kibana) |
| 5 | S9-S10 | ELK-32 à ELK-34 `[T26]`-`[T28]` | À venir (observabilité) |
| 6 | S11-S12 | ELK-35, ELK-36 `[T29]`-`[T30]`* | À venir (tests, CI/CD, livraison) |

\* Numérotation Sprint 6 déduite du décalage Jira ; à confirmer.

## Branches

| Branche | Sprint | Tickets | Fusion |
| --- | --- | --- | --- |
| `sprint-01-analyse` | 1 | ELK-7 à ELK-12 | PR vers `main` |
| `sprint-02-infrastructure` | 2 | ELK-13 à ELK-18 | PR vers `main` |
| `sprint-03-backend` | 3 | ELK-19 à ELK-24 | PR vers `main` |
| `sprint-04-frontend` | 4 | ELK-25 à ELK-31 | PR vers `main` |
| `sprint-05-observabilite` | 5 | ELK-32 à ELK-34 | PR vers `main` |
| `sprint-06-livraison` | 6 | ELK-35, ELK-36 | PR vers `main` |

`main` reste la branche d'intégration : chaque sprint est développé sur sa branche, validé par la CI, puis fusionné via PR ( `--no-ff` ) en conservant la branche.

## Structure du dépôt

```
README.md               ce fichier
.env.example            variables d'environnement (sans secrets)
.gitignore
docker-compose.yml      6 services du socle (ELK-14)
Dockerfile              image Flask python:3.11-slim (ELK-15)
requirements.txt        dépendances Python minimales (ELK-15)
elasticsearch/
  load_templates.sh     chargement des 6 index templates
  templates/            sb-logs-{capteurs,alertes,maintenance,energie,occupation}-*.json et ingest-errors.json
logstash/
  pipeline/             00-bootstrap.conf (ELK-14) ; 05-generated-to-es.conf (ELK-17) ; csv.conf et json.conf (ELK-22) ; TXT converti en CSV avant dépôt
  config/               logstash.yml et pipelines.yml (ELK-14)
mongodb/
  init_mongo.js         base elk_logs : files, searches, thresholds
redis/
  redis.conf            cache (ELK-14)
kibana/
  setup_data_view.sh    data view logs-* (ELK-17)
  dashboards/           exports JSON (ELK-31)
  visualizations/       exports JSON (ELK-31)
app/
  api/ services/ models/ utils/   backend Flask (ELK-19 à ELK-24)
  templates/ static/             frontend Bootstrap 5 (ELK-25 à ELK-31)
  tests/                         pytest (ELK-35)
scripts/
  generate_logs.py      simulateur Faker ~300 capteurs (ELK-16)
data/
  inbox/                dossier surveillé par Logstash (non versionné)
  samples/              fichiers de test CSV/JSON/TXT
  generated/            logs générés (non versionnés)
docs/                   PDFs S1/S2, diagrammes, maquettes, dossier technique
docs/sprints/           un PDF par sprint (S1 à S6)
monitoring/             Prometheus et Grafana (ELK-33, ELK-34)
.github/workflows/      GitHub Actions (ELK-18, ELK-35)
```

## Documentation

- `docs/S1 review.pdf` — analyse fonctionnelle et backlog de 30 tickets (S1).
- `docs/Planning ELK.pdf` — planning 12 semaines, 6 sprints, 183 h.
- `docs/Mini-Projet ELK Oct2026.pdf` — sujet et critères d'évaluation.
- `docs/ELK S2 Architecture et Diagrammes.pdf` — C4, déploiement Docker, séquences (S2).
- `docs/ELK_S2_Mapping_ES_MongoDB_Redis.pdf` — mappings ES, schémas MongoDB, clés Redis (S2).
- `docs/schemas_README.md` — modes d'emploi des templates et du script MongoDB.

## Démarrage rapide

Six services permanents sur le réseau `elk-net` : Elasticsearch 8.17.0, Logstash 8.17.0, Kibana 8.17.0, MongoDB 7, Redis 7 et l'application Flask. Elasticsearch et Kibana démarrent avec `xpack.security.enabled=true` ; les credentials sont lus depuis `.env` (jamais versionné). Le service ponctuel `kibana-setup` configure le mot de passe du compte `kibana_system` avant le démarrage de Kibana.

Prérequis : Docker Engine avec le plugin `docker compose` v2, Python 3 et un shell bash (Linux, macOS, WSL ou Git Bash).

```bash
./scripts/deploy.sh
```

Le script crée `.env` depuis `.env.example` avec des secrets aléatoires si le fichier n'existe pas, lance `docker compose up -d --build`, puis attend que les 6 services permanents soient `healthy` avant d'afficher les URL (US10).

Installation manuelle équivalente :

```bash
cp .env.example .env
# Renseigner ELASTIC_PASSWORD et KIBANA_SYSTEM_PASSWORD dans .env
docker compose up -d --build
docker compose ps
curl -u elastic:$ELASTIC_PASSWORD localhost:9200/_cluster/health
curl localhost:5601/api/status
curl localhost:5000/
curl localhost:5000/health
curl -F "file=@data/samples/capteurs_20261119T195745Z.json" localhost:5000/api/v1/upload
curl localhost:5000/api/v1/files/<file_id>
curl --get localhost:5000/api/v1/search --data-urlencode 'q=temperature' --data-urlencode 'log_type=capteurs' --data-urlencode 'size=10'
curl 'localhost:5000/api/v1/history?page=1&size=10'
curl localhost:5000/docs
curl localhost:5000/openapi.json
```

La documentation interactive Swagger UI est disponible sur `http://localhost:5000/docs` et la spécification OpenAPI sur `http://localhost:5000/openapi.json` (ELK-24). Toutes les routes de l'API sont documentées et exécutables depuis Swagger. Les erreurs suivent un format JSON unique (BNF4) : `{"error":{"code":"...","message":"...","status":400,"detail":{}}}`. Les erreurs APIFlask et Werkzeug (400, 404, 405, 413, 415, 500, 503) passent par le même processeur d'erreur.

Le endpoint `POST /api/v1/upload` valide le format, détecte le type de log, copie le fichier dans `data/inbox/uploads/` avec le statut `ingesting`, puis un polleur Flask interroge Elasticsearch par `source_file_id` pour passer le document à `indexed` dès que `logs_count` événements sont présents (ELK-21). Le endpoint `GET /api/v1/files/<file_id>` retourne les métadonnées, l'aperçu des 10 premières lignes (ELK-20) et le statut d'indexation. Le endpoint `GET /api/v1/search` interroge `sb-logs-*,logs-*` avec `q`, `log_type`, `from`, `to`, `source_file_id`, `severity`, `zone`, `entity_id`, `page`, `size` et `sort` (ELK-23) ; chaque requête est tracée dans la collection Mongo `searches` et consultable via `GET /api/v1/history`. L'endpoint `GET /api/v1/suggest` propose des valeurs réelles issues d'Elasticsearch pendant la saisie, avec repli flou `fuzziness: AUTO`, cache Redis de 30 s et aucune écriture dans l'historique.

Ports exposés : `5000` (Flask), `9200` (Elasticsearch), `5601` (Kibana), `${MONGODB_PORT:-27017}` (MongoDB sur `127.0.0.1` uniquement). Redis et Logstash restent internes au réseau Docker.

- Kibana : `http://localhost:5601`
- Interface web : `http://localhost:5000`
- MongoDB Compass : `mongodb://admin:<MONGO_INITDB_ROOT_PASSWORD>@localhost:${MONGODB_PORT:-27017}/?authSource=admin`, puis base `elk_logs`, collection `files`. Le mot de passe est celui de `.env` ; ne pas le versionner.
- API Logstash (interne) : `http://elk-logstash:9600/_node/pipelines`

Logstash utilise `pipelines.yml` avec quatre pipelines : `bootstrap` (`data/inbox/*.json`, stdout), `generated-to-es` (`data/inbox/generated/*.json`), `uploads-csv` (`data/inbox/uploads/*.csv`) et `uploads-json` (`data/inbox/uploads/*.json`). `06-uploads-to-es.conf` a été supprimé. Les uploads TXT sont convertis en CSV par Flask avant dépôt dans l'inbox, donc aucun fichier n'est ingéré deux fois. `pipeline.workers: 1` reste requis pour l'auto-détection des en-têtes CSV. Les uploads sont indexés dans `sb-logs-<type>-YYYY.MM` (préfixe `sb-logs` pour éviter le template de data stream intégré `logs-*-*` d'Elasticsearch 8) avec `source_file_id`. Les événements invalides sont tagués et envoyés dans `ingest-errors` ; le polleur Flask passe alors le fichier Mongo au statut `failed`. Le marquage des seuils est recalculé si le booléen est absent ou invalide : température > 26, humidité > 65, CO2 > 1000, alertes value > threshold, énergie quantity > 100, maintenance wear_level > 75, occupation occupancy_rate > 80. Les data views `logs-*` et `sb-logs-*` sont créées par `kibana/setup_data_view.sh`.

## Schémas de données (S2)

Règle de conception : Elasticsearch est le seul moteur de recherche ; MongoDB conserve uniquement les métadonnées des fichiers, l'historique des recherches et les seuils ; Redis ne met en cache que des résultats issus d'Elasticsearch.

Chargement manuel des templates (une fois la stack démarrée) :

```bash
export ELASTIC_PASSWORD=...
bash elasticsearch/load_templates.sh
bash kibana/setup_data_view.sh
mongosh "mongodb://admin:PASSWORD@localhost:${MONGODB_PORT:-27017}/?authSource=admin" mongodb/init_mongo.js
```

Les six templates utilisent une priorité 200, 1 shard, 0 réplica et un rafraîchissement à 1 s.

## Vérification ELK-22

```bash
curl -s -u elastic:$ELASTIC_PASSWORD localhost:9200/_cat/indices/sb-logs-*,ingest-errors?v
curl -s -u elastic:$ELASTIC_PASSWORD -H 'Content-Type: application/json' \
  -X POST localhost:9200/sb-logs-*/_count \
  -d '{"query":{"term":{"source_file_id":"<SOURCE_FILE_ID>"}}}'
curl -s -u elastic:$ELASTIC_PASSWORD -H 'Content-Type: application/json' \
  -X POST localhost:9200/ingest-errors/_count \
  -d '{"query":{"term":{"source_file_id":"<SOURCE_FILE_ID>"}}}'
```

Pour chaque upload valide, le compteur `sb-logs-*` doit être égal à `logs_count`, `ingest-errors` doit être à 0 et le document Mongo doit passer à `indexed`. Un upload dont une valeur numérique est invalide doit produire un document dans `ingest-errors` et passer le fichier à `failed`.

## Vérification ELK-23

```bash
curl --get localhost:5000/api/v1/search --data-urlencode 'q=temperature' --data-urlencode 'log_type=capteurs' --data-urlencode 'from=2026-11-21T00:00:00Z' --data-urlencode 'size=10'
curl --get localhost:5000/api/v1/search --data-urlencode 'source_file_id=20261121T083640Z_56a696014a2c'
curl --get localhost:5000/api/v1/search --data-urlencode 'q=temperatur' --data-urlencode 'log_type=capteurs' --data-urlencode 'size=10'
curl 'localhost:5000/api/v1/history?page=1&size=10'
```

La recherche retourne `results`, `total`, `page`, `size`, `took_ms` et `history_id`. Le paramètre `q` est tolérant aux fautes de frappe (`temperatur` trouve `temperature`) et propose cet exemple dans Swagger UI : les correspondances exactes restent prioritaires, puis une requête floue `fuzziness: AUTO` est appliquée. Les filtres `from`/`to` restent inclusifs, acceptent l'ISO-8601 avec `Z` et sont saisis avec un calendrier `datetime-local` dans Swagger UI, converti en UTC avant envoi. `size` est plafonné à 100. Chaque recherche valide ajoute un document dans `searches` avec `cache_hit: false` ; l'historique est trié du plus récent au plus ancien et conservé 90 jours par le TTL MongoDB.

## Vérification ELK-24

Les 7 étapes à exécuter depuis Swagger UI (`http://localhost:5000/docs`) :

1. `GET /health` : réponse `200` avec `status: healthy`.
2. `POST /api/v1/upload` : cliquer sur `Choisir un fichier .csv/.json/.txt`, sélectionner `data/samples/capteurs_20261119T195745Z.json`, puis envoyer ; réponse `201` avec `file_id`. Sous Chrome/Edge, le sélecteur utilise `showOpenFilePicker` avec `excludeAcceptAllOption: true` : l'option `Tous les fichiers` n'apparaît pas et seuls `.csv`, `.json`, `.txt` sont proposés. Dans les autres navigateurs, le champ natif reste filtré et tout autre format est rejeté avant envoi puis par l'API avec un `415` JSON normalisé.
3. `GET /api/v1/files/{file_id}` : réponse `200`, `status: indexed`, `indexed_count` égal à `logs_count`.
4. `GET /api/v1/search` avec `log_type=capteurs` et `size=10` : réponse `200` avec des résultats et un `history_id`.
5. `GET /api/v1/history` : réponse `200` contenant la recherche précédente.
6. `GET /api/v1/files/not-an-object-id` : réponse `400` au format BNF4.
7. `POST /api/v1/upload` avec un fichier de 101 Mo : réponse `413` au format BNF4.

La page Swagger doit afficher la bannière verte `ELK API v1.1.0` ; si l'ancienne page reste affichée, ouvrir `http://localhost:5000/docs?v=10` ou vider le cache du navigateur. Les réponses `/docs` et `/openapi.json` sont désormais envoyées avec `Cache-Control: no-store`.

Vérification rapide en ligne de commande :

```bash
python scripts/check_api_contract.py
curl 'localhost:5000/docs?v=10'
curl localhost:5000/openapi.json
curl -I localhost:5000/docs
truncate -s 101M /tmp/capteurs_trop_gros.csv
curl -F "file=@/tmp/capteurs_trop_gros.csv;filename=capteurs_trop_gros.csv" localhost:5000/api/v1/upload
curl -F "file=@README.md;filename=capteurs_invalide.pdf" localhost:5000/api/v1/upload
```

## Recherche assistée et contraintes d'interface

La page `/search` propose des valeurs indexées pendant la saisie. Le navigateur attend 250 ms, exige au moins 2 caractères, annule les requêtes périmées avec `AbortController` et accepte la navigation au clavier via `role="listbox"`, `aria-activedescendant`, les flèches, Entrée et Échap. Les suggestions proviennent uniquement des champs Elasticsearch réels. Aucune valeur, aucun compteur ni aucun avis n'est inventé dans l'interface.

Le style est volontairement institutionnel : palette neutre, un seul accent bleu, boutons Bootstrap à coin droit, system font, aucun dégradé violet, aucune pilule, aucune image générée, aucune animation de curseur ou de défilement. Les KPI affichent `n/d` lorsqu'une donnée manque, jamais zéro.

La mise en ligne reste subordonnée à quatre éléments : domaine réel avec DNS et TLS, favicon, suppression de tout tag « Made with AI » et pages `/privacy` et `/terms`. Le favicon et les pages légales sont présents. Le tag est absent et vérifié par la CI. Le proxy `proxy` fournit une configuration `server_name ${PUBLIC_DOMAIN}` sous profil Docker, avec `PUBLIC_DOMAIN=localhost` par défaut dans `.env.example`. Il doit être activé et configuré avec un vrai domaine avant publication :

```bash
docker compose --profile proxy up -d proxy
curl localhost:8088/health
```

## Vérification ELK-25 à ELK-31

1. Ouvrir `http://localhost:5000/` : les 5 KPI et les graphiques Chart.js se chargent depuis `/api/v1/stats` ; le badge indique si Redis a servi le cache.
2. Ouvrir `http://localhost:5000/upload` : glisser-déposer un `.csv`, `.json` ou `.txt`, suivre la progression, puis vérifier le `file_id` retourné.
3. Ouvrir `http://localhost:5000/search`, saisir `temperatur` : des valeurs telles que `temperature` apparaissent sous le champ avant la validation. Appuyer sur Entrée pour lancer la recherche : la page `/results` affiche 50 résultats par page, le tri, le détail de chaque document et le bouton d'export CSV.
4. Vérifier les endpoints JSON : `/api/v1/stats`, `/api/v1/maintenance/forecast` et `/api/v1/files`.
5. Créer les data views puis importer le dashboard Kibana :
   ```bash
   bash kibana/setup_data_view.sh
   bash kibana/import_dashboard.sh
   ```
   Le dashboard `Smart Building IoT` contient 3 visualisations : température par zone/heure, alertes critiques par jour et énergie temps réel.
6. Ouvrir une URL inconnue : la page 404 Bootstrap s'affiche ; une URL `/api/v1/...` inconnue renvoie toujours une erreur JSON BNF4.
7. Ouvrir `/privacy` et `/terms` : les deux pages sont accessibles depuis le pied de page et contiennent des champs à renseigner avant publication.
8. Vérifier que le favicon est servi sur `/static/favicon.svg` et qu'aucune page n'affiche de tag « Made with AI ».
9. Vérifier l'autocomplétion au clavier : flèches, Entrée pour sélectionner une suggestion, Échap pour fermer la liste.

Commandes rapides :

```bash
python scripts/check_api_contract.py
curl localhost:5000/
curl localhost:5000/api/v1/stats
curl localhost:5000/api/v1/maintenance/forecast
curl 'localhost:5000/api/v1/suggest?q=temperatur&size=8'
curl 'localhost:5000/api/v1/logs/export?q=temperatur&size=50' -o /tmp/logs-export.csv
bash -n kibana/import_dashboard.sh
```

## Points à consigner suite à la revue n°1

- Port de l'application web : 5000 dans le livrable d'architecture, 8000 dans le sujet. Valeur actuelle : 5000.
- Version ELK figée à 8.17.0 : le layer de l'image 8.19.0 est corrompu dans le cache Docker local.
- Durées de vie Redis appliquées : 60 s pour les KPI généraux, 10 s pour l'énergie temps réel, 300 s pour les prévisions de maintenance et 30 s pour les suggestions ; la recherche complète n'est pas mise en cache. Seuils ELK-22 fixés dans le pipeline Logstash.
