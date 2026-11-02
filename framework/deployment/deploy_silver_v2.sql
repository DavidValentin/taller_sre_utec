-- Create Silver v2 (contract with DQ flags + payload + país)
CREATE TABLE IF NOT EXISTS gameday.silver_customers_v2 (
    ingest_ts TIMESTAMP,
    customer_id STRING,
    customer_name STRING,
    email STRING,
    status STRING,
    payload STRING,
    dq_is_name_null BOOLEAN,
    dq_is_underage BOOLEAN,
    dq_status STRING,
    country_code STRING,
    country_name STRING,
    region STRING
);

-- Gold para Marketing: contactables por país
CREATE TABLE IF NOT EXISTS gameday.gold_contactables_por_pais (
    pais STRING,
    region STRING,
    clientes BIGINT,
    contactables BIGINT,
    pct_contactables DOUBLE,
    updated_ts TIMESTAMP
);

-- Política FinOps: asignar owner y cost center a la tabla Gold para reporte de costos
ALTER TABLE gameday.gold_contactables_por_pais
  SET TAGS ('owner' = 'marketing', 'cost_center' = 'CC-1020', 'consumer' = 'marketing');
