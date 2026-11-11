-- Region 5 · Sales vs Stock raw-data export (one query per refresh)
-- ============================================================================
-- FILTER: change ONLY these two dates to change which SALES months are exported.
-- Stock is always the latest snapshot in the table (lines 'stock' and 'stock_dc').
--   Now:  October + November 2026
--   Example for Nov + Dec:  DATE '2026-11-01'  and  DATE '2026-12-31'
-- ============================================================================
WITH p AS (
  SELECT DATE '2026-10-01' AS sales_from,
         DATE '2026-11-30' AS sales_to
),

src AS (
  SELECT s.*
  FROM `e-smart-433113.region_data.sales_vs_stock_update` s, p
  WHERE (s.line = 'sales' AND s.order_date BETWEEN p.sales_from AND p.sales_to)
     OR (s.line IN ('stock', 'stock_dc')
         AND s.order_date = (SELECT MAX(order_date)
                             FROM `e-smart-433113.region_data.sales_vs_stock_update`
                             WHERE line IN ('stock', 'stock_dc')))
)

SELECT
  s.site_code,
  s.store_name,
  s.order_date,
  IF(s.line = 'sales', CAST(s.month_billing AS STRING), s.line)     AS line,
  s.article_code,
  s.article_description,
  IF(s.Product_Category = 'Device',
     TRIM(CONCAT(IFNULL(TRIM(s.Model_Type_Detail), ''), ' ', IFNULL(TRIM(s.Model_Category), ''))),
     s.article_description)                                          AS `Type 2`,
  s.brandname,
  s.SUM_quantity                                                     AS `Qty`,
  CAST(ROUND(s.SUM_total_nett_amount_exc_tax)  AS INT64)             AS `Nett Exc Tax`,
  CAST(ROUND(s.SUM_total_nett_amount_with_tax) AS INT64)             AS `Nett with Tax`,
  s.week_billing,
  'Region 5'                                                         AS Region,
  s.business_unit,
  s.Product_Category,
  s.ket_po,
  s.territory,
  s.channel,
  s.lob,
  s.tsh,
  s.ROFO_Category,
  s.Detail_Cat,
  s.Model_Type,
  s.Model_Type_Detail                                                AS `Model_Type Detail`,
  s.Model_Category,
  s.Colour
FROM src s
ORDER BY IF(s.line = 'sales', 0, 1), s.line, s.order_date, s.site_code, s.article_code
