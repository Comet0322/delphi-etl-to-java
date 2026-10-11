package etl.units;

import static org.junit.Assert.assertEquals;

import etl.core.Row;
import java.util.List;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

/** ETL-002. Expected values from the legacy output of C01 (T_ORDER_AMT.csv). */
public class OrdersTest {

    private final UnitTestDb db = new UnitTestDb();

    @Before
    public void setUp() throws Exception {
        db.open();
        db.exec("CREATE TABLE ORDERS (ORDER_ID INTEGER, CUST_ID INTEGER, ORDER_DATE REAL,"
                + " QTY INTEGER, UNIT_PRICE REAL, DISCOUNT_PCT INTEGER, NOTE TEXT)");
        // C01 ORDERS rows
        db.exec("INSERT INTO ORDERS VALUES (1, 73, 43001.0, 2, 376.075, 15, NULL)");
        db.exec("INSERT INTO ORDERS VALUES (2, 1, 43002.0, 0, 341.209, 12, 'gift')");
        db.exec("INSERT INTO ORDERS VALUES (9, 18, 43009.0, 24, 12.345, 12, 'gift')");
        db.exec("INSERT INTO ORDERS VALUES (15, 115, 43015.0, 24, 2.5, 10, NULL)");
        db.exec("INSERT INTO ORDERS VALUES (39, 89, 43039.0, 3, 0.125, 12, NULL)");
        db.exec("INSERT INTO ORDERS VALUES (40, 87, 43040.0, 24, 162.535, 0, 'gift')");
        Common.gSkipVoid = true;
    }

    @After
    public void tearDown() throws Exception {
        db.close();
    }

    private List<Row> run() {
        Orders.runOrderAmount();
        return db.rows("SELECT * FROM T_ORDER_AMT_NEW ORDER BY ORDER_ID");
    }

    @Test
    public void rule002_zeroQuantityOrderIsNotWritten() {
        List<Row> r = run();
        assertEquals(5, r.size());
        for (Row row : r) {
            if (((Number) row.get("ORDER_ID")).intValue() == 2) {
                throw new AssertionError("order 2 (QTY 0) must be voided");
            }
        }
    }

    @Test
    public void rule002_nullQuantityIsZeroAndVoided() {
        db.exec("INSERT INTO ORDERS VALUES (99, 1, 0, NULL, 1.0, 0, NULL)");
        assertEquals(5, run().size());
    }

    @Test
    public void rule003_payableAmountRoundedToCentsAsTwoDecimalText() {
        List<Row> r = run();
        assertEquals("639.33", r.get(0).get("AMOUNT"));   // order 1
        assertEquals("260.73", r.get(1).get("AMOUNT"));   // order 9
        assertEquals("54.00", r.get(2).get("AMOUNT"));    // order 15
        assertEquals("0.33", r.get(3).get("AMOUNT"));     // order 39
        assertEquals("3900.84", r.get(4).get("AMOUNT"));  // order 40
    }

    @Test
    public void rule004_statusIsSOnlyAboveTenPercent() {
        List<Row> r = run();
        assertEquals("S", r.get(0).get("STATUS"));   // 15
        assertEquals("N", r.get(2).get("STATUS"));   // 10
        assertEquals("N", r.get(4).get("STATUS"));   // 0
    }

    @Test
    public void implicit_nullNoteWrittenAsEmptyText() {
        List<Row> r = run();
        assertEquals("", r.get(0).get("NOTE"));
        assertEquals("gift", r.get(1).get("NOTE"));
    }
}
