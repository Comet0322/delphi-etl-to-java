package etl.jobs;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import etl.core.DataAccess;
import etl.core.EtlJob;
import etl.core.Row;
import etl.core.Tables;

/** ETL-002 OrderAmount (legacy: uOrders.pas RunOrderAmount). */
public class OrderAmountJob implements EtlJob {

    /** Legacy GSkipVoid, assigned True in TMainForm.FormCreate (LegacyEtl.pas:24). */
    private static final boolean SKIP_VOID = true;

    @Override
    public String id() {
        return "ETL-002";
    }

    @Override
    public void run(DataAccess da) {
        String table = Tables.out("T_ORDER_AMT");                       // ETL-002/OP-07
        da.execute("DROP TABLE IF EXISTS " + table);
        da.execute("CREATE TABLE " + table
                + " (ORDER_ID INTEGER, CUST_ID INTEGER, AMOUNT TEXT, NOTE TEXT, STATUS TEXT)");

        List<Object[]> out = new ArrayList<Object[]>();
        for (Row r : da.query("SELECT ORDER_ID, CUST_ID, QTY, UNIT_PRICE, DISCOUNT_PCT, NOTE "
                + "FROM ORDERS ORDER BY ORDER_ID")) {                   // ETL-002/OP-01
            int qty = intOf(r, "QTY");
            if (SKIP_VOID && qty == 0) {                                // ETL-002/OP-02
                continue;
            }
            int disc = intOf(r, "DISCOUNT_PCT");
            BigDecimal price = currency(r.isNull("UNIT_PRICE") ? 0 : ((Number) r.get("UNIT_PRICE")).doubleValue());
            BigDecimal amt = price.multiply(BigDecimal.valueOf(qty));   // ETL-002/OP-03
            BigDecimal discount = amt.multiply(BigDecimal.valueOf(disc))
                    .divide(BigDecimal.valueOf(100), 4, RoundingMode.HALF_EVEN);
            amt = amt.subtract(discount).setScale(4, RoundingMode.HALF_EVEN);
            long cents = amt.multiply(BigDecimal.valueOf(100)).setScale(0, RoundingMode.HALF_EVEN).longValueExact(); // OP-04
            String status = disc > 10 ? "S" : "N";                      // ETL-002/OP-05
            String note = r.isNull("NOTE") ? "" : r.getString("NOTE");  // ETL-002/OP-06
            out.add(new Object[] {r.getInt("ORDER_ID"), r.getInt("CUST_ID"), centsToStr(cents), note, status});
        }
        da.insertBatch(table, Arrays.asList("ORDER_ID", "CUST_ID", "AMOUNT", "NOTE", "STATUS"), out);
    }

    private static int intOf(Row r, String col) {
        return r.isNull(col) ? 0 : r.getInt(col);
    }

    /** Double to Currency: scaled by 10000 and rounded half to even. */
    private static BigDecimal currency(double d) {
        return BigDecimal.valueOf((long) Math.rint(d * 10000)).movePointLeft(4);
    }

    private static String centsToStr(long cents) {
        String sign = "";
        if (cents < 0) {
            sign = "-";
            cents = -cents;
        }
        return sign + (cents / 100) + "." + String.format("%02d", cents % 100);
    }
}
