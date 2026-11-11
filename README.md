# Region 5 · Sales vs Stock · Raw data download

A static website (GitHub Pages) for downloading raw rows from
`e-smart-433113.region_data.sales_vs_stock_update` as **Excel** or **CSV (zipped)**.
It works like the sbd_vivo dashboard: one BigQuery query per refresh, and you trigger the refresh yourself.

| File | What it is |
|---|---|
| `index.html` | The download page (no external libraries) |
| `sql/export.sql` | The single export query. **Change the sales months here** |
| `scripts/refresh.py` | Dry-runs the query (cost check), runs it with a 2 GB billing cap, builds the `.xlsx`, `.zip` and `meta.json` |
| `.github/workflows/refresh.yml` | The "Refresh data" workflow: export, then deploy to Pages |

**Cost per refresh:** about 0.75 GB scanned (well within BigQuery's 1 TB/month free tier, even with a daily refresh).

The data files are **not stored in git** (the Excel file is about 20 MB). Each run builds them and publishes them straight to Pages.
So any push that changes `index.html`, `sql/`, `scripts/` or the workflow also runs a refresh.

---

## Change the period (backend only)
Open `sql/export.sql` and edit the two dates at the top:

```sql
WITH p AS (
  SELECT DATE '2026-10-01' AS sales_from,
         DATE '2026-11-30' AS sales_to
),
```

Commit the change. The workflow runs and the site updates in about 3 minutes.
Stock always uses the latest snapshot date in the table (`stock` = stores, `stock_dc` = warehouses).

## Output columns
`site_code, store_name, order_date, line, article_code, article_description, Type 2, brandname,
Qty, Nett Exc Tax, Nett with Tax, week_billing, Region, business_unit, Product_Category, ket_po, territory,
channel, lob, tsh, ROFO_Category, Detail_Cat, Model_Type, Model_Type Detail, Model_Category, Colour`

- `line`: for sales rows this is the billing month (`10`, `11`). Stock rows are `stock` (stores) or `stock_dc` (warehouse/DC).
- `Type 2`: for `Product_Category = Device` it is `Model_Type_Detail` + space + `Model_Category` (e.g. "IPHONE 18 PRO MAX 256 GB"); for everything else it is `article_description`.
- `territory` and `ROFO_Category` come straight from the source table.
- `Region` = "Region 5" on every row. Nett values are whole Rupiah. Stock rows have no Nett values.

---

## One-time setup (about 10 minutes)
1. Create a new GitHub repo, e.g. `rcm5DaMon/sales_vs_stock`, and upload all files in this folder.
   Keep the `.github` folder; if you upload through the web page, drag the whole folder in.
2. **Settings → Secrets and variables → Actions → New repository secret**.
   Name: `GCP_SA_KEY`. Value: the **same service-account JSON key you used for sbd_vivo**. It already has
   BigQuery Data Viewer + Job User. The account needs read access to `region_data`.
3. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. If your repo name differs, change `const GITHUB_REPO = "rcm5DaMon/sales_vs_stock";` in `index.html`.
5. **Actions → Refresh data → Run workflow**. After about 3 minutes the site is live at
   `https://rcm5damon.github.io/sales_vs_stock/`.

## Daily use
Click **Refresh data** on the page. GitHub Actions opens: click **Run workflow**, wait about 3 minutes, then reload the page.
For an automatic daily refresh, uncomment the `schedule` block in `.github/workflows/refresh.yml`.

## ⚠ Visibility
GitHub Pages sites are **public** unless your org has GitHub Enterprise Cloud with private Pages.
Anyone with the URL can download this file, which includes store names and sales values. Check with IT before sharing the link.
