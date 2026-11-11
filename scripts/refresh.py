"""Run sql/export.sql once and build the download files for the website.

Output (in site/data/):
  sales_vs_stock_region5.xlsx   Excel, one sheet, full numbers
  sales_vs_stock_region5.zip    the same data as CSV inside a zip (smaller, opens in Excel)
  meta.json                     refresh time, sales period, row counts -> shown on the page

Runs in GitHub Actions (.github/workflows/refresh.yml). Credentials come from the
GCP_SA_KEY secret, so nothing secret is stored in the repo.

Local run (optional):  pip install google-cloud-bigquery openpyxl
                       gcloud auth application-default login
                       python scripts/refresh.py
"""
import csv
import datetime as dt
import io
import json
import os
import pathlib
import re
import sys
import zipfile
from collections import Counter, defaultdict

from google.cloud import bigquery
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "data"
PROJECT = os.environ.get("BQ_PROJECT", "e-smart-433113")
MAX_GB = float(os.environ.get("MAX_GB", "2"))  # safety cap on bytes scanned per refresh
BASENAME = "sales_vs_stock_region5"
WIB = dt.timezone(dt.timedelta(hours=7))

sql = (ROOT / "sql" / "export.sql").read_text(encoding="utf-8")
client = bigquery.Client(project=PROJECT, location="asia-southeast2")

# 1) Dry run = free cost check
dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
gb = dry.total_bytes_processed / 1e9
print(f"Dry run: query will scan {gb:.2f} GB")
if gb > MAX_GB:
    sys.exit(f"Aborting: scan {gb:.2f} GB is above MAX_GB={MAX_GB}. Check sql/export.sql.")

# 2) Real run, capped
job = client.query(sql, job_config=bigquery.QueryJobConfig(
    maximum_bytes_billed=int(MAX_GB * 1e9),
    labels={"app": "sales-vs-stock-download"},
))
result = job.result(page_size=50_000)
headers = [f.name for f in result.schema]
print(f"Billed {job.total_bytes_billed / 1e9:.2f} GB, rows {result.total_rows:,}")

OUT.mkdir(parents=True, exist_ok=True)
xlsx_path = OUT / f"{BASENAME}.xlsx"
zip_path = OUT / f"{BASENAME}.zip"

# Excel (write-only mode keeps memory low)
wb = Workbook(write_only=True)
ws = wb.create_sheet("Data")
widths = {"site_code": 10, "store_name": 34, "order_date": 11, "line": 9, "article_code": 12,
          "article_description": 44, "Type 2": 34, "brandname": 12, "Qty": 8,
          "Nett Exc Tax": 15, "Nett with Tax": 15, "week_billing": 8, "Region": 10,
          "business_unit": 14, "Product_Category": 16, "ket_po": 8, "territory": 18,
          "channel": 16, "lob": 18, "tsh": 22, "ROFO_Category": 18, "Detail_Cat": 16,
          "Model_Type": 20, "Model_Type Detail": 24, "Model_Category": 18, "Colour": 14}
for i, h in enumerate(headers, start=1):
    ws.column_dimensions[get_column_letter(i)].width = widths.get(h, 14)
last_col = get_column_letter(len(headers))
ws.freeze_panes = "A2"
hdr_font, hdr_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F3A5F")
hdr = []
for h in headers:
    c = WriteOnlyCell(ws, value=h)
    c.font, c.fill = hdr_font, hdr_fill
    hdr.append(c)
ws.append(hdr)

date_idx = headers.index("order_date")
num_fmt = {headers.index(h): "#,##0" for h in ("Qty", "Nett Exc Tax", "Nett with Tax")}

csv_buf = io.StringIO()
cw = csv.writer(csv_buf, lineterminator="\r\n")
cw.writerow(headers)

counts, qty = Counter(), defaultdict(int)
line_idx, qty_idx = headers.index("line"), headers.index("Qty")
n_rows = 0
for row in result:
    vals = list(row.values())
    n_rows += 1
    counts[vals[line_idx]] += 1
    qty[vals[line_idx]] += vals[qty_idx] or 0
    cells = []
    for j, v in enumerate(vals):
        if j in num_fmt and v is not None:
            c = WriteOnlyCell(ws, value=v)
            c.number_format = num_fmt[j]
            cells.append(c)
        elif j == date_idx and v is not None:
            c = WriteOnlyCell(ws, value=v)
            c.number_format = "yyyy-mm-dd"
            cells.append(c)
        else:
            cells.append(v)
    ws.append(cells)
    cw.writerow(["" if v is None else (v.isoformat() if j == date_idx else v) for j, v in enumerate(vals)])

ws.auto_filter.ref = f"A1:{last_col}{n_rows + 1}"
wb.save(xlsx_path)

with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    # utf-8-sig adds a BOM so Excel reads the text correctly when the CSV is double-clicked
    z.writestr(f"{BASENAME}.csv", csv_buf.getvalue().encode("utf-8-sig"))

m = re.search(r"DATE '(\d{4}-\d{2}-\d{2})' AS sales_from,\s*DATE '(\d{4}-\d{2}-\d{2})' AS sales_to", sql)
meta = {
    "refreshed_at": dt.datetime.now(WIB).strftime("%Y-%m-%d %H:%M"),
    "sales_from": m.group(1) if m else None,
    "sales_to": m.group(2) if m else None,
    "rows": n_rows,
    "by_line": [{"line": k, "rows": counts[k], "qty": qty[k]}
                for k in sorted(counts, key=lambda k: (not k.isdigit(), k.zfill(2)))],
    "columns": headers,
    "files": {
        "xlsx": {"name": xlsx_path.name, "bytes": xlsx_path.stat().st_size},
        "zip": {"name": zip_path.name, "bytes": zip_path.stat().st_size},
    },
    "billed_gb": round(job.total_bytes_billed / 1e9, 2),
}
(OUT / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
print(json.dumps(meta, indent=1))
