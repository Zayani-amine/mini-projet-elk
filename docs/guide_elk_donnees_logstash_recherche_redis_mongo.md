# Guide ELK : données, Logstash, recherche, Redis et MongoDB

## 1. Objectif du mini-projet

Smart Building IoT est une application de démonstration qui génère, ingère, stocke, recherche et visualise des logs de capteurs et d'équipements. La pile combinée Elasticsearch, Logstash, Kibana, Redis, MongoDB et Flask permet de montrer un cycle complet : données synthétiques, ingestion, indexation, cache, recherche floue, historisation et tableau de bord.

Le guide ci-dessous explique les données réellement produites par le dépôt, les champs disponibles, les règles métier appliquées à l'ingestion et la manière dont les indicateurs du tableau de bord sont calculés.

## 2. Architecture et flux de données

| Composant | Rôle principal | Accès local |
| --- | --- | --- |
| Flask + APIFlask | interface web, API REST v1, documentation Swagger | http://localhost:5000 |
| Elasticsearch | recherche plein texte, agrégations KPI, suggestions | http://localhost:9200 |
| Kibana | tableau de bord Smart Building IoT | http://localhost:5601 |
| Logstash | lecture des fichiers, validation, enrichissement, indexation | interne |
| Redis | cache des suggestions et des KPI | interne |
| MongoDB | métadonnées de fichiers, historique de recherche, seuils | localhost:27018 |
| Nginx | proxy optionnel | http://localhost:8088 |

Le flux complet est le suivant :

- `scripts/generate_logs.py` produit cinq familles de logs au format JSON Lines, CSV ou TXT.
- Les fichiers générés sont copiés dans le dossier d'entrée Logstash.
- Logstash lit les fichiers, convertit les types, applique des règles de seuil, ajoute `source_file_id` et `ingested_at`, puis écrit dans Elasticsearch.
- Les fichiers déposés par l'utilisateur passent par `POST /api/v1/upload`, sont validés puis traités par les pipelines `uploads-csv` et `uploads-json`.
- L'API Flask interroge Elasticsearch pour la recherche et les KPI, utilise Redis pour le cache et MongoDB pour l'historique et les métadonnées.
- Le front-end Chart.js affiche les agrégations renvoyées par `/api/v1/stats`.

## 3. Jeu de données généré

### 3.1 Familles de logs

Le générateur `scripts/generate_logs.py` produit cinq types de logs.

| log_type | Description | Identifiant principal |
| --- | --- | --- |
| `capteurs` | mesures environnementales | `sensor_id` |
| `alertes` | alertes warning ou critical | `alert_id` |
| `energie` | consommation electricity, water, heating | `meter_id` |
| `occupation` | présence et taux d'occupation par salle | `room_id` |
| `maintenance` | usure et prédiction de panne | `equipment_id` |

Les zones utilisées sont `Z1`, `Z2` et `Z3`. Les étages vont de `0` à `3`. Les capteurs sont nommés `CAP-0001`, `CAP-0002`, etc.

### 3.2 Mesures, unités et seuils

| measure | unité | plage générée | warning | critical |
| --- | --- | --- | --- | --- |
| `temperature` | `°C` | 18 à 33 | > 26 | > 30 |
| `humidity` | `%` | 30 à 75 | > 65 | > 75 |
| `luminosity` | `lux` | 100 à 900 | aucun | aucun |
| `co2` | `ppm` | 400 à 1400 | > 1000 | > 1200 |

Les types d'énergie sont `electricity` en `kWh`, `water` en `m3` et `heating` en `kWh`. Les équipements de maintenance sont `hvac`, `pump` et `elevator`.

### 3.3 Champs par famille

`capteurs` contient `@timestamp`, `log_type`, `sensor_id`, `zone`, `floor`, `measure`, `value`, `unit`, `status` et `threshold_breached`. Le champ `status` vaut `ok` ou `faulty`, avec une probabilité de défaut de 0,02.

`alertes` contient `@timestamp`, `log_type`, `alert_id`, `sensor_id`, `zone`, `measure`, `severity`, `rule`, `value` et `threshold`. La règle est construite comme `<measure>_<severity>`. La sévérité est `critical` lorsque la valeur dépasse le seuil critique, sinon `warning`.

`energie` contient `@timestamp`, `log_type`, `meter_id`, `zone`, `energy_type`, `quantity`, `unit` et `threshold_breached`. Le seuil de dépassement est `quantity > 100`.

`occupation` contient `@timestamp`, `log_type`, `room_id`, `zone`, `present_count`, `capacity` et `occupancy_rate`. Le taux est calculé à partir du nombre de personnes présentes et de la capacité de la salle.

`maintenance` contient `@timestamp`, `log_type`, `equipment_id`, `equipment_type`, `zone`, `wear_level`, `predicted_failure` et `estimated_due_date`. Une panne est prédite lorsque `wear_level > 75` et la date estimée se situe entre aujourd'hui et 90 jours dans le futur.

### 3.4 Formats et commande

Les horodatages sont générés en UTC au format ISO-8601 `YYYY-MM-DDTHH:MM:SSZ`. La graine par défaut est `42`, ce qui rend la génération reproductible.

- JSON Lines : un objet JSON par ligne, nommé `<log_type>_<stamp>.json`.
- CSV : séparateur `,`, avec en-tête constitué des clés du premier enregistrement.
- TXT : séparateur `|`, avec en-tête constitué des clés du premier enregistrement.

Commande habituelle :

```bash
python scripts/generate_logs.py --sensors 300 --hours 7 --seed 42 --format all --out data/generated --inbox data/inbox/generated
```

L'option `--inbox` copie uniquement les fichiers JSON générés vers le dossier lu par Logstash.

## 4. Templates et index Elasticsearch

Six templates sont appliqués avec `priority=200`, une version `1`, un shard, zéro réplica et `refresh_interval=1s`. Le mapping dynamique est désactivé afin de contrôler explicitement les champs indexés.

| Modèle d'index | Champs principaux |
| --- | --- |
| `sb-logs-capteurs-*` | `sensor_id`, `zone`, `floor`, `measure`, `value`, `unit`, `status`, `threshold_breached` |
| `sb-logs-alertes-*` | `alert_id`, `sensor_id`, `zone`, `measure`, `severity`, `rule`, `value`, `threshold` |
| `sb-logs-energie-*` | `meter_id`, `zone`, `energy_type`, `quantity`, `unit`, `threshold_breached` |
| `sb-logs-occupation-*` | `room_id`, `zone`, `present_count`, `capacity`, `occupancy_rate` |
| `sb-logs-maintenance-*` | `equipment_id`, `equipment_type`, `zone`, `wear_level`, `predicted_failure`, `estimated_due_date` |
| `ingest-errors` | `source_file_id`, `source_format`, `error_type`, `error_message`, `raw_message`, `tags` |

Tous les index de logs partagent `@timestamp` en `date`, `log_type` en `keyword`, `message` en `text` avec sous-champ `keyword`, `entity_id` comme alias de l'identifiant métier, `source_file_id` en `keyword` et `ingested_at` en `date`.

Point important : les templates ciblent `sb-logs-*`, alors que la pipeline `generated-to-es` écrit dans `logs-*`. La recherche et les agrégations utilisent volontairement le motif combiné `sb-logs-*,logs-*` afin de couvrir les deux familles d'index.

## 5. Pipelines Logstash

Quatre pipelines sont déclarés dans `logstash/config/pipelines.yml`.

| Pipeline | Fichier | Rôle |
| --- | --- | --- |
| `bootstrap` | `00-bootstrap.conf` | lecture initiale des JSON du dossier inbox et affichage stdout |
| `generated-to-es` | `05-generated-to-es.conf` | ingestion des données générées vers `logs-*` |
| `uploads-csv` | `csv.conf` | validation et indexation des fichiers CSV utilisateur |
| `uploads-json` | `json.conf` | validation et indexation des fichiers JSON utilisateur |

Le pipeline généré ajoute `source_file_id` à partir du nom de fichier, `ingested_at` avec la date courante, supprime le champ `path`, puis écrit dans `logs-%{[log_type]}`.

Les pipelines d'upload convertissent les champs numériques attendus : `floor`, `value`, `threshold`, `wear_level`, `quantity`, `present_count`, `capacity` et `occupancy_rate`. Les fichiers invalides sont envoyés dans `ingest-errors` avec `error_type`, `error_message` et `raw_message`.

Les règles de seuil appliquées à l'ingestion sont les suivantes :

- capteurs : `temperature > 26`, `humidity > 65`, `co2 > 1000` ;
- alertes : `value > threshold` ;
- énergie : `quantity > 100` ;
- maintenance : `wear_level > 75` ;
- occupation : `occupancy_rate > 80`.

Les documents valides sont indexés dans `sb-logs-%{[log_type]}-%{+YYYY.MM}`.

## 6. MongoDB

La base `elk_logs` contient trois collections.

| Collection | Contenu |
| --- | --- |
| `files` | métadonnées des fichiers uploadés et état d'indexation |
| `searches` | historique des requêtes de recherche |
| `thresholds` | seuils par mesure et par zone |

`files` exige `original_name`, `stored_name`, `log_type`, `format`, `size_bytes`, `sha256`, `status`, `logs_count`, `uploaded_at` et `updated_at`. Le statut peut valoir `uploaded`, `validated`, `rejected`, `ingesting`, `indexed` ou `failed`. Le champ `sha256` est unique, ce qui évite les doublons. La taille maximale est de 104857600 octets.

`searches` conserve `created_at`, `query`, `filters`, `sort`, `page`, `results_count`, `took_ms` et `cache_hit`. Les filtres couvrent `log_types`, `severity`, `zone`, `entity_id`, `date_from` et `date_to`. Un index TTL supprime les entrées après 90 jours.

`thresholds` contient `measure`, `zone`, `operator`, `critical_value`, `unit`, `enabled` et `updated_at`, avec une valeur warning optionnelle. L'index unique porte sur la paire `measure` et `zone`.

Le script d'initialisation crée les schémas et les index, mais n'insère pas de documents de démonstration.

## 7. Cache Redis

Le client Redis utilise la base `0`, décode les réponses en chaînes et applique un timeout d'une seconde. Les erreurs Redis sont ignorées afin de ne pas faire échouer l'API.

Les clés sont construites avec `make_key(prefix, payload)` : un SHA-1 du JSON trié du payload, préfixé par le nom de la fonction.

| Usage | Préfixe | TTL |
| --- | --- | --- |
| Suggestions | `elk:suggest:v1:` | 30 secondes |
| Température | `elk:kpi:v3:<period>:temperature_avg` | 60 secondes |
| Alertes critiques | `elk:kpi:v3:<period>:critical_alerts_24h` | 60 secondes |
| Énergie | `elk:kpi:v3:<period>:energy_realtime` | 10 secondes |
| Occupation | `elk:kpi:v3:<period>:occupancy_rate` | 60 secondes |
| Maintenance | `elk:kpi:v3:maintenance_forecast` | 300 secondes |

Le champ `cache_hit` de la réponse `/api/v1/stats` indique quels KPI proviennent du cache. Le badge du tableau de bord affiche le nombre de KPI servis depuis Redis sur cinq.

## 8. API et recherche

L'application expose une API REST version `1.1.0` sous `/api/v1` et une documentation Swagger sur `/docs`.

| Route | Rôle |
| --- | --- |
| `GET /health` | healthcheck du service web |
| `GET /api/v1/search` | recherche paginée dans les logs |
| `GET /api/v1/suggest` | suggestions pour la barre de recherche |
| `GET /api/v1/history` | historique des recherches |
| `GET /api/v1/stats` | indicateurs du tableau de bord |
| `GET /api/v1/maintenance/forecast` | prévisions de maintenance |
| `GET /api/v1/logs/export` | export CSV, limité à 10000 logs |
| `POST /api/v1/upload` | dépôt d'un fichier csv, json ou txt |
| `GET /api/v1/files` | liste des fichiers uploadés |

Les paramètres de recherche sont `q`, `log_type`, `from`, `to`, `source_file_id`, `severity`, `zone`, `entity_id`, `page`, `size` et `sort`. Le champ `entity_id` est un alias de `sensor_id`, `meter_id`, `room_id` ou `equipment_id`.

La requête Elasticsearch combine deux niveaux :

- une correspondance exacte avec boost, notamment sur `entity_id^5`, `message.keyword^4`, `message^3`, `zone^2` et `severity^2` ;
- une correspondance floue avec `fuzziness=AUTO`, `prefix_length=1` et `max_expansions=50`.

Chaque recherche est enregistrée dans MongoDB. Les suggestions ne sont pas historisées et nécessitent au moins deux caractères. Le front-end déclenche les suggestions après 250 ms, annule la requête précédente et permet une navigation au clavier.

## 9. Tableau de bord et explication des données

### 9.1 Périodes disponibles

| Valeur | Libellé affiché | Durée | Intervalle d'agrégation |
| --- | --- | --- | --- |
| `1h` | `1h` | 1 heure | `1m` |
| `24h` | `24h` | 24 heures | `1h` |
| `7d` | `7j` | 7 jours | `1h` |
| `30d` | `30j` | 30 jours | `1d` |
| `custom` | `Personnalisé` | jusqu'à 90 jours | dynamique |

Pour une période personnalisée, les paramètres `from` et `to` sont obligatoires. L'intervalle devient `1m` en dessous de deux heures, `1h` en dessous de trois jours, puis `1d`.

### 9.2 Calcul des indicateurs

| Indicateur | Calcul | Données affichées |
| --- | --- | --- |
| Température | `avg(value)` filtré sur `measure=temperature` | moyenne globale en °C et moyenne par zone |
| Alertes critiques | `date_histogram` filtré sur `severity=critical` | somme des counts et série temporelle |
| Énergie | `sum(quantity)` par unité et par bucket | total kWh, dernier relevé, âge du relevé et consommation d'eau en m3 |
| Occupation | `avg(occupancy_rate)` global et par salle | taux global en pourcentage et répartition par salle |
| Maintenance | documents `predicted_failure=true` avec date future | nombre d'équipements et détail par équipement |

La température, les alertes, l'énergie et l'occupation dépendent de la période sélectionnée. La maintenance est calculée sur les prédictions futures et n'est pas recalculée par période.

### 9.3 Graphiques

Le graphique de température affiche les moyennes par zone. Le graphique d'alertes affiche l'évolution du nombre d'alertes critiques. Le graphique d'énergie affiche uniquement les buckets `kWh`. Le graphique d'occupation affiche la répartition par salle. Le graphique de maintenance affiche les équipements dont la panne est prédite.

Le message « Aucune donnée disponible pour cette période » n'apparaît que lorsque le conteneur du graphique porte la classe `chart-empty`. Lorsque des données sont présentes, ce message est masqué et le graphique est rendu normalement.

### 9.4 Lecture des résultats

Une valeur `n/d` signifie que l'agrégation ne contient pas de mesure exploitable pour la période demandée. Un badge de cache indique combien de KPI ont été servis depuis Redis. Une alerte critique affichée dans la barre supérieure provient de l'appel `/api/v1/stats` sans paramètre, donc de la période `7j` par défaut.

## 10. Exploitation et vérification

Le déploiement standard reconstruit l'image webapp puis démarre la pile :

```bash
cd /home/zayani/mini-projet-elk
bash scripts/deploy.sh
docker compose --profile proxy up -d proxy
```

Vérifications utiles :

```bash
curl http://localhost:5000/health
curl http://localhost:5000/api/v1/stats?period=7d
curl http://localhost:8088/health
docker compose ps
```

La documentation Swagger est disponible sur `/docs`. Les contrôles automatisés vérifient les contrats d'API, les artefacts Kibana, les marqueurs d'accessibilité, les règles visuelles et la cohérence de la pile Docker.

## 11. Limites et améliorations possibles

Le jeu de données est synthétique et reproductible ; il ne représente pas un bâtiment réel. Le motif d'index `logs-*` utilisé par la pipeline générée diffère du motif `sb-logs-*` des templates, mais la recherche couvre les deux. Les seuils de maintenance et d'occupation sont appliqués à l'ingestion plutôt que modifiés dynamiquement depuis MongoDB. Enfin, le cache Redis peut retarder de quelques secondes la visibilité d'une donnée fraîchement indexée, notamment pour l'énergie dont le TTL est de 10 secondes.
