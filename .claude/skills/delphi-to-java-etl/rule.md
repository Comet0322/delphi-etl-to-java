# Rules

**Legacy behavior is the specification.** Preserve it, quirks included. Do not
fix what looks like a bug; report it. Java 8 only (no `var`, `List.of`).

## Structure
- One legacy ETL = one `EtlJob`. Jobs use only `DataAccess`, never `java.sql`.
- Outputs go to `Tables.out(...)`; never write a plain-named table.
- Comment each step with its `op_id` (e.g. `// ETL-001/OP-03`).
- Libraries: JDK, JDBC driver, JUnit 4. Nothing else without the user's say.
- SQL parameters are bound, never concatenated.

## Delphi semantics that change results if translated naively
- **Currency**: fixed-point, 4 decimals → `BigDecimal` scale 4, never `double`.
  Re-apply `setScale(4, ...)` after each operation as Delphi does.
- **Round()**: banker's rounding (half to even) → `RoundingMode.HALF_EVEN`.
  `Math.round` is wrong. `Trunc` → `RoundingMode.DOWN`. Keep the legacy order
  of rounding (per step vs at the end).
- **TDateTime**: days since 1899-12-30; `0` is 1899-12-30 and is usually the
  "no date" marker. `1900-01-01` may also be a sentinel. Map to null only
  where legacy treats it as empty, and write back what legacy wrote.
- **Strings are 1-based**: `Copy(s,i,n)` ≠ `substring(i,…)`; `Pos` returns 0
  (not -1) when missing; `Copy` never throws on out-of-range.
- **CHAR(n)**: values come back right-padded with spaces. Trim only where
  legacy trims. Delphi `Trim` strips chars ≤ `#32` only.
- **Big5/CP950**: use the charset legacy assumed (`MS950` for CP950). In an
  ANSI string, `Length` counts bytes (a Chinese char is 2); do length/pad
  arithmetic on bytes when legacy does. Never assume UTF-8 for legacy files.
- **Null vs '' vs 0**: `Field.AsString` on NULL gives `''`, `AsInteger` gives
  `0` — legacy using `As*` already collapsed NULL; legacy testing `IsNull`
  first did not. Mirror exactly. Oracle treats `''` as NULL in VARCHAR2.
- **div/mod**: `div` truncates toward zero; `/` is always floating.
- **Row order** often comes from a dataset index (`IndexFieldNames`), not an
  `ORDER BY`. If output order matters, reproduce the ordering explicitly.
- **Swallowed exceptions** (`try … except end`) silently skip rows; keep that.

## Where hidden logic lives (read all of it)
Event handlers (`FormCreate`, `OnClick`, `OnTimer`, `BeforePost`,
`OnCalcFields`), unit-level globals and `initialization`, dataset properties
(`Filter`, `MasterSource`, `Sort`), calculated/lookup fields in the `.dfm`,
`with` blocks.
