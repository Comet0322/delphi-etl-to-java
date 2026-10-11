package etl.units;

import static org.junit.Assert.assertEquals;

import etl.core.Row;
import java.util.List;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

/** ETL-003. Expected values from the legacy output of C01 (T_CITY_SUM.csv). */
public class CitySumTest {

    private final UnitTestDb db = new UnitTestDb();

    @Before
    public void setUp() throws Exception {
        db.open();
        db.exec("CREATE TABLE T_CUST_CLEAN_NEW (CUST_ID INTEGER, NAME TEXT, CITY TEXT, JOIN_DATE TEXT, NOTE TEXT)");
        db.exec("CREATE TABLE T_ORDER_AMT_NEW (ORDER_ID INTEGER, CUST_ID INTEGER, AMOUNT TEXT, NOTE TEXT, STATUS TEXT)");
    }

    @After
    public void tearDown() throws Exception {
        db.close();
    }

    private void cust(int id, String city) {
        db.exec("INSERT INTO T_CUST_CLEAN_NEW VALUES (?, 'n', ?, '', '')", id, city);
    }

    private void order(int id, int cust, String amt) {
        db.exec("INSERT INTO T_ORDER_AMT_NEW VALUES (?, ?, ?, '', 'N')", id, cust, amt);
    }

    private List<Row> run() {
        CitySum.runCitySum();
        return db.rows("SELECT * FROM T_CITY_SUM_NEW");
    }

    @Test
    public void rule007_countAndCurrencyTotalPerCityInLegacySortOrder() {
        // The C01 city set; legacy wrote them in this order:
        // HSINCHU, KAOHSIUNG, TAICHUNG, TAINAN, TAIPEI, (UNKNOWN), ZüRICH, 台南
        cust(1, "台南");
        cust(2, "ZüRICH");
        cust(3, "TAIPEI");
        cust(4, "TAINAN");
        cust(5, "TAICHUNG");
        cust(6, "KAOHSIUNG");
        cust(7, "HSINCHU");
        order(1, 1, "10.10");
        order(2, 2, "1.05");
        order(3, 99, "2.00");
        order(4, 3, "0.33");
        order(5, 4, "3.00");
        order(6, 5, "4.00");
        order(7, 6, "5.00");
        order(8, 7, "6.00");
        order(9, 1, "0.90");
        List<Row> r = run();
        String[] cities = {"HSINCHU", "KAOHSIUNG", "TAICHUNG", "TAINAN", "TAIPEI", "(UNKNOWN)", "ZüRICH", "台南"};
        assertEquals(cities.length, r.size());
        for (int i = 0; i < cities.length; i++) {
            assertEquals(cities[i], r.get(i).get("CITY"));
        }
        assertEquals(2, ((Number) r.get(7).get("ORDER_CNT")).intValue());
        assertEquals("11.00", r.get(7).get("TOTAL"));
        assertEquals("0.33", r.get(4).get("TOTAL"));
    }

    @Test
    public void rule008_missingCustomerOrEmptyCityIsUnknown() {
        cust(1, "");
        order(1, 1, "1.00");
        order(2, 42, "2.50");
        List<Row> r = run();
        assertEquals(1, r.size());
        assertEquals("(UNKNOWN)", r.get(0).get("CITY"));
        assertEquals(2, ((Number) r.get(0).get("ORDER_CNT")).intValue());
        assertEquals("3.50", r.get(0).get("TOTAL"));
    }

    @Test
    public void rule009_totalWrittenWithTwoDecimals() {
        cust(1, "TAIPEI");
        order(1, 1, "54.00");
        order(2, 1, "0.33");
        List<Row> r = run();
        assertEquals("54.33", r.get(0).get("TOTAL"));
    }
}
