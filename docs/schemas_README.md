# Schémas de données - ELK-11 [T05]

Fichiers prêts à l'emploi pour les semaines S3-S4. Les index templates ont été chargés et validés dans le ticket ELK-17 [T11] une fois la stack démarrée.

## Elasticsearch

    export ELASTIC_PASSWORD=...        # voir .env
    bash elasticsearch/load_templates.sh

Vérification :

    curl -u elastic:$ELASTIC_PASSWORD localhost:9200/_index_template/logs-capteurs?pretty

Les templates ont la priorité 200 : Elasticsearch 8 fournit un template intégré pour `logs-*-*` de priorité 100. Les patterns `logs-<type>` évitent volontairement ce masque pour conserver des index classiques et non des data streams.

## Kibana

    bash kibana/setup_data_view.sh

Crée la data view `logs-*` avec `@timestamp` comme champ temporel. Le script est idempotent : si la vue existe déjà, il ne fait rien.

Logstash indexe les JSONL générés dans `logs-<type>` via `logstash/pipeline/05-generated-to-es.conf`. Les champs `ingested_at` et `source_file_id` sont ajoutés côté Logstash.

## MongoDB

    mongosh "mongodb://USER:PASSWORD@localhost:27017/?authSource=admin" mongodb/init_mongo.js

Crée la base `elk_logs` avec les collections `files`, `searches`, `thresholds` (validateurs JSON Schema et index).
