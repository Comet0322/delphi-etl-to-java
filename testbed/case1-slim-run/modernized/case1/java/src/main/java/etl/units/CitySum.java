package etl.units;

import etl.core.Db;
import etl.core.Row;
import etl.core.Tables;
import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** uCitySum.pas: order count and total amount per customer city (depends on uCustomer and uOrders output). */
public final class CitySum {

    private CitySum() {
    }

    /** TCityAcc. */
    public static class CityAcc {
        public int cnt;
        public BigDecimal total;

        public CityAcc() {
            cnt = 0;
            total = BigDecimal.ZERO.setScale(4);
        }
    }

    /** RunCitySum. */
    public static void runCitySum() {
        Map<String, String> cityOf;
        TreeMap<String, CityAcc> acc;
        List<Row> q;
        String city;
        CityAcc a;
        cityOf = new LinkedHashMap<String, String>();
        // Sorted := True, Duplicates := dupIgnore, CaseSensitive = False: AnsiCompareText order, first spelling kept
        acc = new TreeMap<String, CityAcc>(DelphiRtl.ANSI_COMPARE_TEXT);
        try {
            // ETL-003/OP-01
            q = Db.current().query("SELECT CUST_ID, CITY FROM " + Tables.out("T_CUST_CLEAN"));
            for (Row r : q) {
                Customer.valuesPut(cityOf, DelphiRtl.asString(r.get("CUST_ID")), DelphiRtl.asString(r.get("CITY")));
            }

            // ETL-003/OP-02
            q = Db.current().query("SELECT CUST_ID, AMOUNT FROM " + Tables.out("T_ORDER_AMT"));
            for (Row r : q) {
                city = Customer.valuesGet(cityOf, DelphiRtl.asString(r.get("CUST_ID")));
                if (city.isEmpty()) {
                    city = "(UNKNOWN)";
                }
                a = acc.get(city);                      // Idx := Acc.IndexOf(City)
                if (a == null) {
                    a = new CityAcc();
                    acc.put(city, a);                   // Acc.AddObject(City, A)
                }
                a.cnt += 1;
                a.total = DelphiRtl.curr(a.total.add(DelphiRtl.strToCurr(DelphiRtl.asString(r.get("AMOUNT")))));
            }

            // ETL-003/OP-03
            Db.current().execute("DROP TABLE IF EXISTS " + Tables.out("T_CITY_SUM"));
            Db.current().execute("CREATE TABLE " + Tables.out("T_CITY_SUM")
                    + " (CITY TEXT, ORDER_CNT INTEGER, TOTAL TEXT)");
            // ETL-003/OP-04
            for (Map.Entry<String, CityAcc> e : acc.entrySet()) {
                a = e.getValue();
                Db.current().execute("INSERT INTO " + Tables.out("T_CITY_SUM") + " VALUES (?, ?, ?)",
                        e.getKey(), a.cnt, DelphiRtl.currToStrFFixed(a.total, 2));
            }
        } finally {
            // Acc.Free, CityOf.Free
        }
    }
}
