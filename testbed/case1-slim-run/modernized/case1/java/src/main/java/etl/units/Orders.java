package etl.units;

import etl.core.Db;
import etl.core.Row;
import etl.core.Tables;
import java.math.BigDecimal;
import java.util.List;

/** uOrders.pas: compute the payable amount of each order. */
public final class Orders {

    private Orders() {
    }

    /** CentsToStr. */
    public static String centsToStr(long cents) {
        String sign;
        // ETL-002/OP-05
        sign = "";
        if (cents < 0) {
            sign = "-";
            cents = -cents;
        }
        return sign + DelphiRtl.intToStr(cents / 100) + "." + DelphiRtl.formatD2(cents % 100);
    }

    /** RunOrderAmount. */
    public static void runOrderAmount() {
        List<Row> q;
        int qty;
        int disc;
        BigDecimal price;
        BigDecimal amt;
        String status;
        // ETL-002/OP-01
        Db.current().execute("DROP TABLE IF EXISTS " + Tables.out("T_ORDER_AMT"));
        Db.current().execute("CREATE TABLE " + Tables.out("T_ORDER_AMT")
                + " (ORDER_ID INTEGER, CUST_ID INTEGER, AMOUNT TEXT, NOTE TEXT, STATUS TEXT)");
        // ETL-002/OP-02
        q = Db.current().query(
                "SELECT ORDER_ID, CUST_ID, QTY, UNIT_PRICE, DISCOUNT_PCT, NOTE FROM ORDERS ORDER BY ORDER_ID");
        for (Row r : q) {
            qty = DelphiRtl.asInteger(r.get("QTY"));
            if (Common.gSkipVoid && (qty == 0)) {
                continue;
            }
            // ETL-002/OP-03
            price = DelphiRtl.asCurrency(r.get("UNIT_PRICE"));
            disc = DelphiRtl.asInteger(r.get("DISCOUNT_PCT"));
            amt = DelphiRtl.curr(BigDecimal.valueOf(qty).multiply(price));
            amt = DelphiRtl.curr(amt.subtract(amt.multiply(BigDecimal.valueOf(disc)).divide(BigDecimal.valueOf(100))));
            // ETL-002/OP-04
            if (disc > 10) {
                status = "S";
            } else {
                status = "N";
            }
            // ETL-002/OP-06
            Db.current().execute("INSERT INTO " + Tables.out("T_ORDER_AMT") + " VALUES (?, ?, ?, ?, ?)",
                    DelphiRtl.asInteger(r.get("ORDER_ID")),
                    DelphiRtl.asInteger(r.get("CUST_ID")),
                    // ETL-002/OP-05
                    centsToStr(DelphiRtl.round(DelphiRtl.curr(amt.multiply(BigDecimal.valueOf(100))))),
                    DelphiRtl.asString(r.get("NOTE")),
                    status);
        }
    }
}
