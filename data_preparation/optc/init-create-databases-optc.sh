#!/bin/bash
# Create OpTC databases + tables (same 4-table schema as the TC datasets).
# Additive sibling of ../postgres/init-create-databases.sh — does NOT touch TC databases.
#
#   ./init-create-databases-optc.sh                       # original names (optc_h201, ...)
#   ./init-create-databases-optc.sh _Test_for_OpenSource  # isolated suffixed copies
set -e

SUFFIX="${1:-}"

echo "Starting OpTC database and table creation (suffix='${SUFFIX}')..."

for dataset in optc_h201 optc_h051 optc_h501
do
    DATASET_NAME=$(echo "${dataset}${SUFFIX}" | tr '[:upper:]' '[:lower:]')
    echo "Creating database and tables for: $DATASET_NAME"

    psql -U postgres <<EOF
CREATE DATABASE $DATASET_NAME;
\c $DATASET_NAME;

CREATE TABLE event_table (
    src_node VARCHAR,
    src_index_id VARCHAR,
    operation VARCHAR,
    dst_node VARCHAR,
    dst_index_id VARCHAR,
    event_uuid VARCHAR NOT NULL,
    timestamp_rec BIGINT,
    _id SERIAL PRIMARY KEY
);
ALTER TABLE event_table OWNER TO postgres;
CREATE UNIQUE INDEX event_table__id_uindex ON event_table (_id);
GRANT DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON event_table TO postgres;

CREATE TABLE file_node_table (
    node_uuid VARCHAR NOT NULL,
    hash_id VARCHAR NOT NULL,
    path VARCHAR,
    index_id BIGINT,
    PRIMARY KEY (node_uuid, hash_id)
);
ALTER TABLE file_node_table OWNER TO postgres;

CREATE TABLE netflow_node_table (
    node_uuid VARCHAR NOT NULL,
    hash_id VARCHAR NOT NULL,
    src_addr VARCHAR,
    src_port VARCHAR,
    dst_addr VARCHAR,
    dst_port VARCHAR,
    index_id BIGINT,
    PRIMARY KEY (node_uuid, hash_id)
);
ALTER TABLE netflow_node_table OWNER TO postgres;

CREATE TABLE subject_node_table (
    node_uuid VARCHAR,
    hash_id VARCHAR,
    path VARCHAR,
    cmd VARCHAR,
    index_id BIGINT,
    PRIMARY KEY (node_uuid, hash_id)
);
ALTER TABLE subject_node_table OWNER TO postgres;
EOF

    echo "Database '$DATASET_NAME' created successfully."
done

echo "All OpTC databases created."
