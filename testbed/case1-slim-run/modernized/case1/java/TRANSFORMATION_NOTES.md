# Transformation notes: case1

Legacy: `legacy/case1/*.pas` (Free Pascal, `{$mode delphi}`). Java: `src/main/java/etl/...` (paths below relative to
`src/main/java`). RTL routines are in `etl/units/DelphiRtl.java` (rule.md §5, §6).

## uCommon → etl.units.Common

| Routine / global | Legacy | Java |
|---|---|---|
| `GSkipVoid` | uCommon.pas:12 | etl/units/Common.java:11 (`gSkipVoid`) |
| `GConn`, `GTrans` | uCommon.pas:10-11 | none: they only held the connection / transaction (rule.md §2) |

Replaced routines (not translated):

| Routine | Legacy | Capability | Target |
|---|---|---|---|
| `OpenDb` | uCommon.pas:21-29 | db.connect | `Db.open(p)` in `BatchRun.formCreate` |
| `CloseDb` | uCommon.pas:31-35 | db.commit + db.disconnect | `Db.commit()` in `BatchRun.buttonRunClick`; `Db.close()` in `BatchRun.main` finally |
| `ExecSql` | uCommon.pas:37-40 | db.exec | `Db.current().execute(sql)` |
| `NewQuery` | uCommon.pas:42-48 | db.query / db.write | `Db.current().query(sql)` / `Db.current().execute("INSERT ...", params)` |

## uCustomer → etl.units.Customer

| Routine | Legacy | Java |
|---|---|---|
| `LoadNotes` | uCustomer.pas:18-40 | etl/units/Customer.java:26-52 |
| `RunCustomerClean` | uCustomer.pas:42-81 | etl/units/Customer.java:55-91 |
| TStringList `Values[k] := v` / `Values[k]` (helpers) | uCustomer.pas:35,72 | etl/units/Customer.java:94-106 (`valuesPut`, `valuesGet`) |
| `AssignFile/Reset/ReadLn` (file.read.text) | uCustomer.pas:24-29 | etl/units/Customer.java:109-136 (`readLines`, bytes) |

- The notes file is handled as bytes: `Length`, `Copy` and `Trim` count bytes; bytes 5-24 are decoded with the MS950
  decoder (REPLACE, `?`) as the legacy `SetCodePage(Note, 950)` + `SetCodePage(Note, CP_UTF8, True)` did.
- `Notes.Values[k] := ''` deletes the entry, so a blank note line removes an earlier note for the same id (kept).
- `StrToIntDef(..., 0)`: a non-numeric id maps every such line to key `0` (kept; a customer with CUST_ID 0 or NULL
  gets that note).
- A NULL `JOIN_DATE` reads as 0 and gives `''`, like 0 (kept).

## uOrders → etl.units.Orders

| Routine | Legacy | Java |
|---|---|---|
| `CentsToStr` | uOrders.pas:15-26 | etl/units/Orders.java:16-25 |
| `RunOrderAmount` | uOrders.pas:28-63 | etl/units/Orders.java:28-66 |

- Currency is `BigDecimal` scale 4 HALF_EVEN after each operation; `UNIT_PRICE` (REAL) is read `AsCurrency`, i.e.
  the exact double rounded to 4 decimals. `Amt * Disc / 100` is computed exactly and rounded to 4 decimals at the
  assignment (DECISIONS D-007). `Round` is half to even.
- A NULL `QTY` reads as 0 and is voided like 0 (kept).

## uCitySum → etl.units.CitySum

| Routine / type | Legacy | Java |
|---|---|---|
| `TCityAcc` (class) | uCitySum.pas:17-20 | etl/units/CitySum.java:19-27 (`CityAcc`) |
| `RunCitySum` | uCitySum.pas:22-83 | etl/units/CitySum.java:30-75 |

- `Acc` is a sorted `TStringList` (dupIgnore, CaseSensitive False): a `TreeMap` with `DelphiRtl.ANSI_COMPARE_TEXT`,
  first spelling kept. FPC's `AnsiCompareText` under cwstring upper-cases and calls glibc `strcoll` in the
  process locale (en_US.UTF-8), which ignores punctuation at the first level: `(UNKNOWN)` sorts between `TAIPEI`
  and `ZüRICH`. `DelphiRtl.ansiCompareText` reproduces this (DECISIONS D-006).
- `CityOf` is an unsorted `TStringList` used through `Values`: an empty city deletes the entry, so the order counts
  under `(UNKNOWN)` (kept). `T_CUST_CLEAN` and `T_ORDER_AMT` are read without ORDER BY, as in the legacy.
- `CurrToStrF(Total, ffFixed, 2)`: fixed two decimals, no thousand separator.

## LegacyEtl.pas (program, TMainForm) → etl.BatchRun

| Legacy | Java |
|---|---|
| program block, LegacyEtl.pas:36-44 | etl/BatchRun.java:44-50 (`run`); `DefaultSystemCodePage := CP_UTF8` needs nothing (Java strings are Unicode) |
| `TMainForm.FormCreate`, LegacyEtl.pas:20-26 | etl/BatchRun.java:53-58 (`formCreate`): `ParamStr(1)` = `jdbc.url`, `ParamStr(2)` = `notes.file`, `GSkipVoid := True`, `OpenDb` = `Db.open(p)` |
| `TMainForm.ButtonRunClick`, LegacyEtl.pas:28-34 | etl/BatchRun.java:61-66 (`buttonRunClick`): Customer, Orders, CitySum, `CloseDb` = `Db.commit()` |
| `FDb`, `FNotes` | static fields `fDb`, `fNotes` |
| `Form`, `TMainForm.Create/Free` | none (static handlers, rule.md §1) |

## Legacy bugs and quirks kept

- Blank note line deletes the customer's note; non-numeric note ids collapse onto id 0.
- NULL quantity orders are voided; NULL dates print as empty.
- City order follows the locale collation of the legacy run, not code-point order.
