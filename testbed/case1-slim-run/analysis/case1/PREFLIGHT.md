# Preflight - case1 (written before any other analyze artifact)

Date: 2026-10-11

- ✅ Legacy source `legacy/case1` (5 Pascal files: LegacyEtl.pas, uCommon, uCustomer, uOrders, uCitySum) contains no data and no build output; only `.pas` files.
- ✅ Free Pascal 3.2.2 is available (`fpc -Mdelphi`); legacy builds into `analysis/case1/build/legacy`, outside the source.
- ✅ Java 8: `/home/linuxbrew/.linuxbrew/opt/openjdk@8` (1.8.0_504); Maven 3.9.12.
- ✅ Input folder holds `legacy.db` (CUSTOMER, ORDERS) and `cust_notes.txt` (Big5); no `recorded/` outputs, so the legacy runs here (not recorded).
- ✅ Template project from domain knowledge copied to `modernized/case1/java/` (build result recorded in step 1 below).
- Legacy outputs: T_CUST_CLEAN, T_ORDER_AMT, T_CITY_SUM (written into the database given as argument 1).
