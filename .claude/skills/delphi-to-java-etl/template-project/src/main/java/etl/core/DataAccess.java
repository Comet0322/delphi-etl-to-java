package etl.core;

import java.util.List;

/**
 * The only way a job touches the database. In the company environment the
 * implementation delegates to the internal Oracle wrapper library.
 */
public interface DataAccess {

    List<Row> query(String sql, Object... params);

    /** First column of the first row, or null when there is no row. */
    Object queryScalar(String sql, Object... params);

    int execute(String sql, Object... params);

    int insertBatch(String table, List<String> columns, List<Object[]> rows);

    /** Commits when the work returns, rolls back when it throws. */
    void inTransaction(Runnable work);
}
