package etl.core;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.fail;

import java.io.File;
import java.util.Properties;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

public class DbTest {

    private File file;
    private Properties p;

    @Before
    public void setUp() throws Exception {
        file = File.createTempFile("dbtest", ".db");
        p = new Properties();
        p.setProperty("jdbc.url", "jdbc:sqlite:" + file.getAbsolutePath());
        p.setProperty("table.suffix", "_X");
    }

    @After
    public void tearDown() {
        Db.close();
        file.delete();
    }

    @Test
    public void commitKeepsWorkAndCloseWithoutCommitDiscardsIt() {
        Db.open(p);
        Db.current().execute("CREATE TABLE T (ID INTEGER)");
        Db.current().execute("INSERT INTO T VALUES (1)");
        Db.commit();
        Db.current().execute("INSERT INTO T VALUES (2)");
        Db.close();
        Db.open(p);
        assertEquals(1, ((Number) Db.current().queryScalar("SELECT COUNT(*) FROM T")).intValue());
        assertEquals("T_A_X", Tables.out("T_A"));
    }

    @Test
    public void currentWithoutOpenFails() {
        try {
            Db.current();
            fail();
        } catch (EtlException expected) {
            // BatchRun must open first
        }
    }
}
