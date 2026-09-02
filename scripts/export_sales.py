import pandas as pd
import psycopg
from dotenv import load_dotenv
import os

# Load .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL belum ditemukan di file .env")

QUERY = """
SELECT *
FROM esb_data.v_sales_recap_detail
WHERE sales_date >= TIMESTAMP '2026-08-01 00:00:00'
  AND sales_date <  TIMESTAMP '2026-08-30 00:00:00'
ORDER BY sales_date ASC;
"""

OUTPUT_FILE = "v_sales_recap_detail_2026-08-01_2026-08-30.xlsx"


def main():
    print("Menghubungkan ke database...")

    with psycopg.connect(DATABASE_URL) as conn:
        print("Connected.")

        with conn.cursor() as cur:
            print("Mengambil data...")

            cur.execute(QUERY)

            columns = [desc.name for desc in cur.description]
            rows = cur.fetchall()

    print(f"Data berhasil diambil: {len(rows):,} rows")

    df = pd.DataFrame(rows, columns=columns)

    print("Membuat file Excel...")

    df.to_excel(
        OUTPUT_FILE,
        index=False,
        engine="openpyxl"
    )

    print()
    print("===================================")
    print("EXPORT BERHASIL")
    print("===================================")
    print(f"File    : {OUTPUT_FILE}")
    print(f"Rows    : {len(df):,}")
    print(f"Columns : {len(df.columns):,}")
    print("===================================")


if __name__ == "__main__":
    main()