package etl.core;

/** One migrated legacy ETL. Annotate each step with its operation id. */
public interface EtlJob {

    /** Stable id of the legacy ETL, e.g. "ETL-001". */
    String id();

    void run(DataAccess da);
}
