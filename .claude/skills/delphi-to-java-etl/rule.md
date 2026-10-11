# Mapping rules: Delphi ETL → Java 8

What each Delphi construct becomes in this project's Java. Apply every rule exactly; where a rule and a habit of
"good Java" disagree, the rule wins. A legacy bug is translated as it is and reported.

Target: Java 8 (no `var`, `List.of`, records), Maven, JUnit 4. Libraries: JDK, the JDBC driver, JUnit 4.

## 1. Structure (one to one, no refactoring)

| Delphi | Java |
|---|---|
| unit `uOrders.pas` | class `etl.units.Orders` (drop a leading lower-case `u`; otherwise the same name) |
| procedure / function `RunOrderAmount(A, B)` | `public static` method `runOrderAmount(a, b)`: lowerCamel name, same parameters in the same order, same return |
| local `var` block | locals declared at the top of the method, same names in lowerCamel |
| unit-level variable `GSkipVoid` | `public static` field `Common.gSkipVoid` |
| unit-level `const` | `static final` field, same name |
| `initialization` section | `static void initialization()`, called by BatchRun where the legacy ran it |
| nested procedure | `private static` method `<outer>_<inner>` |
| `var` / `out` parameter | one-element array or holder at the same position |
| `type TCityAcc = record … end` | `public static final class CityAcc` nested in the unit's class (drop the `T`), same fields in lowerCamel, no-argument constructor zeroing them |
| `type TKind = (kA, kB)` | nested `enum Kind { kA, kB }`, same order (`Ord` = `ordinal()`) |
| `type TFoo = class … end` (not a form) | nested `public static class Foo`, same fields and methods |
| program block, form class `TMainForm`, its handlers | `etl.BatchRun`; handlers become static methods of the same name (`formCreate`, `buttonRunClick`) |
| statement order inside a routine | the same order; nothing merged, split, extracted or reordered |
| each inventory operation | its statements headed `// ETL-001/OP-03` |

## 2. Capabilities (infrastructure → designated target)

Whatever the legacy used for a capability — a VCL/BDE/ADO/dbExpress/SQLdb/FireDAC component, a third-party
library, or a routine written inside the project — the Java uses the target below.

- **replace**: the legacy code for it is not translated; callers call the target.
- **keep**: the business code around the call (row loop, SQL text, field conversions) is translated one to one;
  only the infrastructure call becomes the target.
- **In-project helpers**: a routine whose whole body is infrastructure (`OpenDb`, `CloseDb`, `ExecSql`, `NewQuery`,
  `RunSQL`) is always replaced, whatever the action below; a global that only holds a connection or transaction
  (`GConn`, `GTrans`, `DM.DB`) disappears. A routine mixing business logic and infrastructure is translated with
  only the calls swapped.
- **Not listed**: an infrastructure call no row covers is a decision for a person. Unattended default: translate
  with the JDK only, no new library, and record the decision.

| Capability | Recognize in the legacy | Java target | Action | Only in |
|---|---|---|---|---|
| db.connect | connection components (`TDatabase`, `TADOConnection`, `TSQLConnection`, `TSQLite3Connection`, `TFDConnection`…): create, set DatabaseName/ConnectionString, `Open`, `Connected := True`; data module `OnCreate` | `Db.open(props)` (jdbc.url / jdbc.user / jdbc.password in etl.properties) | replace | BatchRun |
| db.commit | `Commit`, `CommitRetaining`, a close routine that commits | `Db.commit()` at the same place | replace | BatchRun |
| db.rollback | `Rollback`, `RollbackRetaining` | `Db.rollback()` | replace | BatchRun |
| db.disconnect | `Close`, `Connected := False`, freeing the connection | nothing: `BatchRun.main` calls `Db.close()` in `finally` | replace | — |
| db.transaction | `StartTransaction … Commit/Rollback` around a block inside the run | `Db.current().inTransaction(() -> { … })` | keep | — |
| db.query | `TQuery`/`TADOQuery`/`TSQLQuery`/`TFDQuery`: `SQL.Text`, `Params`, `Open`, `First/Next/Eof`; `TTable` with `IndexFieldNames`/`Filter` | `Db.current().query(sql, params…)` → `List<Row>`; `queryScalar` for one value; `TTable` becomes a SELECT with that ORDER BY / WHERE | keep | — |
| db.exec | `ExecSQL`, `ExecuteDirect`, `TADOCommand.Execute` | `Db.current().execute(sql, params…)` | keep | — |
| db.write | `Insert/Append/Edit` + field assignments + `Post`, `AppendRecord`, INSERT in a loop | `Db.current().insertBatch(Tables.out(t), columns, rows)` or `execute(...)` | keep | — |
| config.read | `ParamStr`, `ParamCount`, `TIniFile`/`TRegistry` reads, environment variables | a key in etl.properties, read in BatchRun and passed on as the legacy passed it | replace | BatchRun |
| file.read.text | `AssignFile/Reset/ReadLn`, `TStringList.LoadFromFile`, `TFileStream` | `java.nio` / `BufferedReader` with the charset of §6; `byte[]` where the legacy works on bytes | keep | — |
| file.write.text | `AssignFile/Rewrite/WriteLn`, `TStringList.SaveToFile` | `java.nio` / `BufferedWriter`, same charset and line ending | keep | — |
| log | `WriteLn` to the console, a log unit, `OutputDebugString` | `java.util.logging.Logger` named after the class | keep | — |
| ui | `ShowMessage`, `MessageDlg`, progress bars, `Application.ProcessMessages` | nothing; a message reporting a result becomes a log line. A dialog that asks a question is a decision for a person | replace | — |

Never `java.sql` outside `etl.core`. SQL parameters are bound, never concatenated.

## 3. Tables

| Delphi | Java |
|---|---|
| output table (written, created, dropped, emptied) | `Tables.out("T_X")` everywhere it is named, including DDL |
| input table, or another ETL's output used as input | input: plain name; another ETL's output: `Tables.out("T_X")` (this run's result) |

## 4. Types

| Delphi | Java |
|---|---|
| `Integer`, `Cardinal`, `Word`, `Byte`, `SmallInt` | `int` |
| `Int64` | `long` |
| `Currency` | `BigDecimal`, `setScale(4, HALF_EVEN)` after every operation, in the legacy order |
| `Double`, `Extended`, `Real`, `Single` | `double` |
| `TDateTime` | `double` (days since 1899-12-30); `0` and NULL stay as the legacy treats them; convert only where the legacy formats or compares |
| `Boolean` | `boolean` |
| `string` holding database text | `String` |
| `AnsiString` / `RawByteString` read from a legacy file | `byte[]` while the legacy works on bytes (`Length`, `Copy`, padding count bytes); decode per §6 when it becomes text |
| `Char` | `char` (`byte` for an ANSI byte) |
| integer `div` / `mod` | `/` / `%` on integers (both truncate toward zero) |
| `/` | floating division (`double`) |

## 5. RTL routines → `etl.units.DelphiRtl`

One static method per routine, same name, written once with this behavior:

| Delphi | `DelphiRtl` behavior |
|---|---|
| `Round(x)` | half to even (`RoundingMode.HALF_EVEN`) |
| `Trunc(x)` | toward zero (`RoundingMode.DOWN`) |
| `Copy(s, i, n)` | 1-based; out-of-range start or count is clamped; never throws |
| `Pos(sub, s)` | 1-based index; `0` when absent |
| `Length(s)` | characters for `String`, bytes for a `byte[]` ANSI value |
| `Trim`, `TrimLeft`, `TrimRight` | strip characters `<= #32` only |
| `UpperCase`, `LowerCase` | ASCII letters only |
| `AnsiUpperCase`, `AnsiLowerCase` | full case mapping |
| `StrToInt`, `StrToIntDef(s, d)` | `StrToIntDef` returns `d` on any parse failure |
| `IntToStr`, `FloatToStr`, `FormatFloat`, `FormatDateTime` | the same text the legacy produces for the values in the input domain |
| `Inc`, `Dec` | `+= 1`, `-= 1` |

## 6. Field access, NULL, charset, order, errors

| Delphi | Java |
|---|---|
| `FieldByName(F).AsString` | `DelphiRtl.asString(row.get("F"))`: NULL → `""` |
| `.AsInteger` | `DelphiRtl.asInteger(...)`: NULL → `0` |
| `.AsFloat`, `.AsDateTime` | `DelphiRtl.asFloat(...)`: NULL → `0.0` |
| `.AsCurrency` | `DelphiRtl.asCurrency(...)`: NULL → `0`, scale 4 |
| `.IsNull` | `row.get("F") == null` |
| `.Value` / Variant | keep NULL as `null` |
| writing `''` to a VARCHAR2 on Oracle | write `""` as the legacy did (Oracle stores NULL) |
| text file in Big5 / CP950 | charset `MS950`; decode with a `CharsetDecoder` set to `REPLACE` and `replaceWith("?")` (a double-byte character cut by a byte-wise `Copy` becomes `?`, as in the legacy); never `new String(bytes, cs)` (gives U+FFFD) |
| dataset order from `IndexFieldNames`, `Sort`, a TTable index | `ORDER BY` on the same fields |
| `TStringList` with `Sorted := True` / `Values[...]` | `TreeMap` / `LinkedHashMap` reproducing the same order and duplicate handling |
| `try … except end` that swallows | `try { … } catch (RuntimeException e) { }` around the same statements |
| `raise` | `throw new EtlException(...)` |

## 7. Structure checks

Checked by a script after the transform, against the Java under `src/main/java` (paths relative to it). Kinds:
`only-in` the pattern may appear only in the listed paths; `never` it may appear nowhere (`{TABLE}` stands for each
output table); `same-as-template` the listed paths equal the template's; `exists` the listed files exist. A `\|`
inside a pattern is a regex `|`.

| Check | Kind | Pattern | Paths |
|---|---|---|---|
| connection opened and committed only by BatchRun | only-in | `\bDb\.(open\|commit\|rollback)\s*\(` | `etl/BatchRun.java` |
| no JDBC outside etl.core | only-in | `\bjava\.sql\b\|\bDriverManager\b` | `etl/core/` |
| etl.core unchanged | same-as-template | | `etl/core/` |
| output tables only through Tables.out | never | `\b(INSERT\s+INTO\|UPDATE\|DELETE\s+FROM\|DROP\s+TABLE(\s+IF\s+EXISTS)?\|CREATE\s+TABLE)\s+{TABLE}\b` | |
| entry point exists | exists | | `etl/BatchRun.java` |

## 8. Fresh-input categories

Edge cases the fresh inputs must cover in this project, besides the general ones (NULL versus empty versus zero,
values at and beside each threshold, rounding ties, empty tables, duplicate keys, rows referencing a missing parent,
large values, empty input files).

| Category | Cover |
|---|---|
| date_sentinels | `TDateTime` `0`, NULL and `1900-01-01` in every date column read |
| char_spaces | CHAR values with leading, trailing and only spaces |
| charset_bytes | Big5 text whose byte length crosses a fixed width or a `Copy` boundary, including a double-byte character cut in half |
