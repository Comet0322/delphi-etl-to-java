package etl.core;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.fail;

import java.sql.Connection;
import java.sql.DriverManager;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

public class JdbcDataAccessTest {

    private Connection conn;
    private DataAccess da;

    @Before
    public void setUp() throws Exception {
        conn = DriverManager.getConnection("jdbc:sqlite::memory:");
        da = new JdbcDataAccess(conn);
        da.execute("CREATE TABLE T (ID INTEGER, NAME TEXT)");
    }

    @After
    public void tearDown() throws Exception {
        conn.close();
    }

    @Test
    public void batchInsertAndQuery() {
        da.insertBatch("T", Arrays.asList("ID", "NAME"),
                Arrays.asList(new Object[] {1, "a"}, new Object[] {2, null}));
        List<Row> rows = da.query("SELECT * FROM T ORDER BY ID");
        assertEquals(2, rows.size());
        assertEquals("a", rows.get(0).getString("name"));
        assertNull(rows.get(1).get("NAME"));
    }

    @Test
    public void transactionRollsBackOnFailure() {
        try {
            da.inTransaction(new Runnable() {
                public void run() {
                    da.execute("INSERT INTO T VALUES (1, 'x')");
                    throw new IllegalStateException("boom");
                }
            });
            fail();
        } catch (IllegalStateException expected) {
            // expected
        }
        assertEquals(0, ((Number) da.queryScalar("SELECT COUNT(*) FROM T")).intValue());
    }

    @Test
    public void suffixAppliedInOnePlace() {
        Tables.setSuffix("_NEW");
        assertEquals("T_ORDER_NEW", Tables.out("T_ORDER"));
        assertEquals(Collections.emptyList(), da.query("SELECT * FROM T"));
    }
}
