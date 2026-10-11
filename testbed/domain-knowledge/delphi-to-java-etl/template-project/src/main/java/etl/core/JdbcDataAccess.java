package etl.core;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;

/** JDBC-backed DataAccess used by the testbed. */
public class JdbcDataAccess implements DataAccess {

    private final Connection conn;

    public JdbcDataAccess(Connection conn) {
        this.conn = conn;
    }

    @Override
    public List<Row> query(String sql, Object... params) {
        try (PreparedStatement ps = prepare(sql, params); ResultSet rs = ps.executeQuery()) {
            ResultSetMetaData md = rs.getMetaData();
            List<Row> rows = new ArrayList<Row>();
            while (rs.next()) {
                Row row = new Row();
                for (int i = 1; i <= md.getColumnCount(); i++) {
                    row.put(md.getColumnLabel(i), rs.getObject(i));
                }
                rows.add(row);
            }
            return rows;
        } catch (SQLException e) {
            throw new EtlException("query failed: " + sql, e);
        }
    }

    @Override
    public Object queryScalar(String sql, Object... params) {
        List<Row> rows = query(sql, params);
        if (rows.isEmpty()) {
            return null;
        }
        return rows.get(0).asMap().values().iterator().next();
    }

    @Override
    public int execute(String sql, Object... params) {
        try (PreparedStatement ps = prepare(sql, params)) {
            return ps.executeUpdate();
        } catch (SQLException e) {
            throw new EtlException("execute failed: " + sql, e);
        }
    }

    @Override
    public int insertBatch(String table, List<String> columns, List<Object[]> rows) {
        StringBuilder marks = new StringBuilder();
        for (int i = 0; i < columns.size(); i++) {
            marks.append(i == 0 ? "?" : ",?");
        }
        String sql = "INSERT INTO " + table + " (" + String.join(",", columns) + ") VALUES (" + marks + ")";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            for (Object[] row : rows) {
                for (int i = 0; i < row.length; i++) {
                    ps.setObject(i + 1, row[i]);
                }
                ps.addBatch();
            }
            int n = 0;
            for (int c : ps.executeBatch()) {
                n += c < 0 ? 1 : c;
            }
            return n;
        } catch (SQLException e) {
            throw new EtlException("batch insert failed: " + table, e);
        }
    }

    @Override
    public void inTransaction(Runnable work) {
        try {
            boolean auto = conn.getAutoCommit();
            conn.setAutoCommit(false);
            try {
                work.run();
                conn.commit();
            } catch (RuntimeException e) {
                conn.rollback();
                throw e;
            } finally {
                conn.setAutoCommit(auto);
            }
        } catch (SQLException e) {
            throw new EtlException("transaction failed", e);
        }
    }

    private PreparedStatement prepare(String sql, Object[] params) throws SQLException {
        PreparedStatement ps = conn.prepareStatement(sql);
        for (int i = 0; i < params.length; i++) {
            ps.setObject(i + 1, params[i]);
        }
        return ps;
    }
}
