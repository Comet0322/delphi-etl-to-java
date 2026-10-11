package etl.core;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.Properties;

/**
 * The designated way to connect (capability db.connect in capabilities.yaml). Only BatchRun opens and
 * closes; every migrated method takes the connection from {@link #current()}, the way Delphi code used a
 * global connection component. In the company environment {@link #open} delegates to the internal Oracle
 * wrapper library; nothing else changes between environments.
 *
 * <p>The connection starts one transaction, as a Delphi dataset transaction does: {@link #commit()} makes the
 * work permanent, {@link #close()} without a commit discards it.
 */
public final class Db {

    private static DataAccess current;
    private static Connection conn;

    private Db() {
    }

    /** Opens the connection from jdbc.url / jdbc.user / jdbc.password and applies table.suffix. */
    public static DataAccess open(Properties p) {
        if (current != null) {
            throw new EtlException("Db.open called twice without Db.close");
        }
        Tables.setSuffix(p.getProperty("table.suffix", "_NEW"));
        try {
            conn = DriverManager.getConnection(
                    p.getProperty("jdbc.url"), p.getProperty("jdbc.user"), p.getProperty("jdbc.password"));
            conn.setAutoCommit(false);
        } catch (SQLException e) {
            throw new EtlException("cannot open " + p.getProperty("jdbc.url"), e);
        }
        current = new JdbcDataAccess(conn);
        return current;
    }

    /** The open connection. */
    public static DataAccess current() {
        if (current == null) {
            throw new EtlException("no open connection: BatchRun must call Db.open first");
        }
        return current;
    }

    /** For tests: use a connection that someone else opened. */
    public static void setCurrent(DataAccess da) {
        current = da;
        conn = null;
    }

    public static void commit() {
        try {
            if (conn != null) {
                conn.commit();
            }
        } catch (SQLException e) {
            throw new EtlException("commit failed", e);
        }
    }

    public static void rollback() {
        try {
            if (conn != null) {
                conn.rollback();
            }
        } catch (SQLException e) {
            throw new EtlException("rollback failed", e);
        }
    }

    /** Closes without committing. Safe to call when nothing is open. */
    public static void close() {
        try {
            if (conn != null) {
                conn.rollback();
                conn.close();
            }
        } catch (SQLException e) {
            throw new EtlException("close failed", e);
        } finally {
            conn = null;
            current = null;
        }
    }
}
