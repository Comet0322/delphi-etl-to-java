---
name: delphi-to-java-etl
description: Domain knowledge for migrating small Delphi ETL programs to Java 8. Describes the template project (DataAccess wrapper, old/new table suffix), how to use it, and how to handle each legacy feature. Use when analyzing, clarifying or converting a Delphi ETL migration. Behavior rules are in rule.md.
---

# Delphi → Java ETL

Two things come with this skill: `template-project/` and `rule.md`.

## Template design

Maven, Java 8, JUnit 4. `etl.core` is infrastructure, `etl.jobs` is where
migrated ETLs go.

- `DataAccess`: the only way to touch the database (query, queryScalar,
  execute, insertBatch, inTransaction). In the company it wraps the internal
  Oracle library; here `JdbcDataAccess` backs it with JDBC. Only that
  implementation changes between environments.
- `Tables.out(name)`: the single place the old/new suffix (`_NEW`) is
  applied. Migrated output goes to `<TABLE>_NEW`; plain `<TABLE>` is the
  legacy baseline and is read-only.
- `EtlJob`: one class per legacy ETL, `id()` + `run(DataAccess)`.
- `EtlRunner`: registers jobs in dependency order, reads `etl.properties`
  (`jdbc.url`, `jdbc.user`, `jdbc.password`, `table.suffix`).

## How to use

1. Copy `template-project/` to the target dir; change `groupId`/`artifactId`.
2. Do not edit `etl.core` unless an ETL cannot be written otherwise.
3. Add `etl.jobs.<Name>Job implements EtlJob`; register it in `EtlRunner.jobs()`
   after the jobs it depends on.
4. Run: `mvn -q package`, then
   `java -cp target/classes:target/lib/* etl.core.EtlRunner etl.properties`.

## Legacy feature → how to handle

| You see in the Delphi source | Do |
|---|---|
| Query/Table/ADO/BDE dataset read | `da.query(...)`, read inputs by plain name |
| `Post`/`Insert`/`ExecSQL` writing results | `da.insertBatch(Tables.out(t), ...)` / `da.execute(...)` |
| Several writes that must go together | `da.inTransaction(...)` |
| `Currency` / money arithmetic | `BigDecimal`, scale 4 (see rule.md) |
| `Round`, `Trunc`, `FormatFloat` | see rule.md |
| `TDateTime`, `0` as empty date | see rule.md |
| `CHAR(n)` columns, `Trim`, Big5 files | see rule.md |
| `IsNull`, `AsString`, Variant Null | see rule.md |
| Logic in `FormCreate`/`OnClick`/globals | part of the ETL; inventory it, implement it |
| Another unit's output used as input | job order in `EtlRunner`; read it via `Tables.out(...)` |
| Writes a file (CSV/fixed width) | not covered here: ask (default: `java.io`/`java.nio` only) |
| Scheduling, logging, config | not covered here: ask (defaults: run on demand, `java.util.logging`, `etl.properties`) |
