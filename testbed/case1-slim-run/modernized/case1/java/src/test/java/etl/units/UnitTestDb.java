package etl.units;

import etl.core.Db;
import etl.core.JdbcDataAccess;
import etl.core.Row;
import etl.core.Tables;
import java.sql.Connection;
import java.sql.DriverManager;
import java.util.List;

/** Temporary in-memory SQLite database installed as Db.current() (SKILL.md test pattern). */
final class UnitTestDb {

    private Connection conn;

    void open() throws Exception {
        conn = DriverManager.getConnection("jdbc:sqlite::memory:");
        Db.setCurrent(new JdbcDataAccess(conn));
        Tables.setSuffix("_NEW");
    }

    void close() throws Exception {
        Db.setCurrent(null);
        conn.close();
    }

    void exec(String sql, Object... params) {
        Db.current().execute(sql, params);
    }

    List<Row> rows(String sql) {
        return Db.current().query(sql);
    }
}
