package etl.jobs;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import etl.core.DataAccess;
import etl.core.EtlJob;
import etl.core.Row;
import etl.core.Tables;

/** ETL-003 CitySummary (legacy: uCitySum.pas RunCitySum). Depends on ETL-001 and ETL-002. */
public class CitySummaryJob implements EtlJob {

    private static final class Acc {
        int count;
        BigDecimal total = BigDecimal.ZERO;
    }

    @Override
    public String id() {
        return "ETL-003";
    }

    @Override
    public void run(DataAccess da) {
        Map<String, String> cityOf = new HashMap<String, String>();    // ETL-003/OP-01
        for (Row r : da.query("SELECT CUST_ID, CITY FROM " + Tables.out("T_CUST_CLEAN"))) {
            cityOf.put(r.getString("CUST_ID"), r.getString("CITY"));
        }

        // legacy TStringList: Sorted, default (case-insensitive) comparison
        Map<String, Acc> acc = new TreeMap<String, Acc>(String.CASE_INSENSITIVE_ORDER);
        for (Row r : da.query("SELECT CUST_ID, AMOUNT FROM " + Tables.out("T_ORDER_AMT"))) { // OP-02
            String city = cityOf.get(r.getString("CUST_ID"));           // ETL-003/OP-03
            if (city == null || city.isEmpty()) {
                city = "(UNKNOWN)";
            }
            Acc a = acc.get(city);                                      // ETL-003/OP-04
            if (a == null) {
                a = new Acc();
                acc.put(city, a);
            }
            a.count++;
            a.total = a.total.add(new BigDecimal(r.getString("AMOUNT")));
        }

        String table = Tables.out("T_CITY_SUM");                        // ETL-003/OP-05
        da.execute("DROP TABLE IF EXISTS " + table);
        da.execute("CREATE TABLE " + table + " (CITY TEXT, ORDER_CNT INTEGER, TOTAL TEXT)");
        List<Object[]> out = new ArrayList<Object[]>();
        for (Map.Entry<String, Acc> e : acc.entrySet()) {
            out.add(new Object[] {e.getKey(), e.getValue().count,
                    e.getValue().total.setScale(2, RoundingMode.HALF_EVEN).toPlainString()});
        }
        da.insertBatch(table, Arrays.asList("CITY", "ORDER_CNT", "TOTAL"), out);
    }
}
