import os
import sys
from databricks import sql
from datetime import datetime, timezone

HOST = os.environ["DATABRICKS_HOST"]
HTTP_PATH = os.environ["DATABRICKS_HTTP_PATH"]
TOKEN = os.environ["DATABRICKS_TOKEN"]

RUN_ID = os.environ.get("RUN_ID", "manual")
SILVER_TABLE = os.environ.get("SILVER_TABLE", "gameday.silver_customers_v2")

def fetch_one(cur, stmt: str):
    cur.execute(stmt)
    return cur.fetchall()[0][0]

def main():
    checked_at = datetime.now(timezone.utc).isoformat()
    print(f"✅ Validating table: {SILVER_TABLE}")
    print(f"✅ RUN_ID: {RUN_ID}")

    with sql.connect(server_hostname=HOST, http_path=HTTP_PATH, access_token=TOKEN) as conn:
        with conn.cursor() as cur:
            total = fetch_one(cur, f"SELECT COUNT(*) FROM {SILVER_TABLE}")
            name_null = fetch_one(cur, f"SELECT COUNT(*) FROM {SILVER_TABLE} WHERE dq_is_name_null = true")
            underage = fetch_one(cur, f"SELECT COUNT(*) FROM {SILVER_TABLE} WHERE dq_is_underage = true")

            # Check preventivo: Consistencia de país y región según estándar ISO
            # Frena el pipeline si algún cliente tiene mapeo erróneo o país nulo (ej. CL mapeado a Perú)
            country_mismatch = fetch_one(cur, f"""
                SELECT COUNT(*) FROM {SILVER_TABLE}
                WHERE country_name IS NULL
                   OR (country_code = 'CL' AND country_name != 'Chile')
                   OR (country_code = 'PE' AND country_name != 'Perú')
                   OR (country_code = 'AR' AND country_name != 'Argentina')
                   OR (country_code = 'CO' AND country_name != 'Colombia')
            """)

            # Guarda resultados en ops_dq_results
            cur.execute(
                "INSERT INTO gameday.ops_dq_results VALUES (?, current_timestamp(), ?, 'total_rows', 'INFO', ?, ?)",
                (RUN_ID, SILVER_TABLE, float(total), f"checked_at={checked_at}")
            )

            cur.execute(
                "INSERT INTO gameday.ops_dq_results VALUES (?, current_timestamp(), ?, 'name_null_count', ?, ?, ?)",
                (RUN_ID, SILVER_TABLE, "FAIL" if name_null > 0 else "PASS", float(name_null), "name is null/empty")
            )

            cur.execute(
                "INSERT INTO gameday.ops_dq_results VALUES (?, current_timestamp(), ?, 'underage_count', ?, ?, ?)",
                (RUN_ID, SILVER_TABLE, "WARN" if underage > 0 else "PASS", float(underage), "age < 18")
            )

            cur.execute(
                "INSERT INTO gameday.ops_dq_results VALUES (?, current_timestamp(), ?, 'country_consistency_check', ?, ?, ?)",
                (RUN_ID, SILVER_TABLE, "FAIL" if country_mismatch > 0 else "PASS", float(country_mismatch), "country_code vs country_name mismatch or null")
            )

    print(f"✅ Validation completed: total={total}, name_null={name_null}, underage={underage}, country_mismatch={country_mismatch}")

    if country_mismatch > 0:
        print(f"❌ DQ Error: {country_mismatch} registro(s) con inconsistencia de país en {SILVER_TABLE}. Frenando pipeline antes de Gold.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
