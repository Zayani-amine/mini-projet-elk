# Mini-Projet ELK — Monitoring et analyse de logs (Smart Building IoT)

IT Business School — Zayani Mohamed Amine — Encadrant : Mohamed Najeh ISSAOUI

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
| 2 | S3-S4 | ELK-13 à ELK-18 `[T07]`-`[T12]` | En cours : ELK-13 terminé ; ELK-14 à ELK-18 à faire |
| 3 | S5-S6 | ELK-19 à ELK-24 `[T13]`-`[T18]` | À venir (upload, ingestion, recherche, API) |
| 4 | S7-S8 | ELK-25 à ELK-31 `[T19]`-`[T25]` | À venir (frontend et Kibana) |
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
docker-compose.yml      6 services du socle (ELK-14, à venir)
Dockerfile              image Flask (ELK-15, à venir)
requirements.txt        dépendances Python (ELK-15, à venir)
elasticsearch/
  load_templates.sh     chargement des 5 index templates
  templates/            logs-{capteurs,alertes,maintenance,energie,occupation}.json
logstash/
  pipeline/             00-bootstrap.conf (ELK-14) ; csv.conf et json.conf (ELK-22)
  config/               logstash.yml et pipelines.yml (ELK-14)
mongodb/
  init_mongo.js         base elk_logs : files, searches, thresholds
redis/
  redis.conf            cache (ELK-14)
kibana/
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

Disponible après ELK-14 et ELK-15 :

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
curl localhost:5000/health
```

Kibana : `http://localhost:5601`. Interface web : `http://localhost:5000`.

## Schémas de données (S2)

Règle de conception : Elasticsearch est le seul moteur de recherche ; MongoDB conserve uniquement les métadonnées des fichiers, l'historique des recherches et les seuils ; Redis ne met en cache que des résultats issus d'Elasticsearch.

Chargement manuel des templates (une fois la stack démarrée) :

```bash
export ELASTIC_PASSWORD=...
bash elasticsearch/load_templates.sh
mongosh "mongodb://admin:PASSWORD@localhost:27017/?authSource=admin" mongodb/init_mongo.js
```

Les templates utilisent une priorité 200, 1 shard, 0 réplica et un rafraîchissement à 1 s.

## Points à consigner suite à la revue n°1

- Port de l'application web : 5000 dans le livrable d'architecture, 8000 dans le sujet. Valeur actuelle : 5000.
- Durées de vie Redis (60 s / 10 s / 300 s) et valeurs de seuils à confirmer avec l'encadrant.
