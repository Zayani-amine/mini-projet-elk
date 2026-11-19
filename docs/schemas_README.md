# Schémas de données - ELK-11 [T05]

Fichiers prêts à l'emploi pour les semaines S3-S4. Ils n'ont pas été testés sur un cluster en fonctionnement :
à valider dans le ticket ELK-17 [T11] (index templates) une fois la stack démarrée.

## Elasticsearch

    export ELASTIC_PASSWORD=...        # voir .env
    bash elasticsearch/load_templates.sh

Vérification :

    curl -u elastic:$ELASTIC_PASSWORD localhost:9200/_index_template/logs-capteurs?pretty

Les templates ont la priorité 200 : Elasticsearch 8 fournit un template intégré pour `logs-*-*` de priorité 100.

## MongoDB

    mongosh "mongodb://USER:PASSWORD@localhost:27017/?authSource=admin" mongodb/init_mongo.js

Crée la base `elk_logs` avec les collections `files`, `searches`, `thresholds` (validateurs JSON Schema et index).
