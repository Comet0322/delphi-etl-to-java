package etl;

import etl.core.Db;
import etl.units.CitySum;
import etl.units.Common;
import etl.units.Customer;
import etl.units.Orders;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;

/**
 * Entry point and the one place that opens the database. Mirrors LegacyEtl.pas: the program block, then
 * TMainForm.FormCreate and TMainForm.ButtonRunClick, calling the migrated unit classes in the legacy order.
 * Set a breakpoint in {@link #run} to step through a batch the way the Delphi IDE would.
 *
 * <p>Usage: {@code java -cp target/classes:target/lib/* etl.BatchRun etl.properties}. ParamStr(1) is jdbc.url,
 * ParamStr(2) is notes.file.
 */
public final class BatchRun {

    /** TMainForm.FDb (ParamStr(1)). */
    static String fDb;
    /** TMainForm.FNotes (ParamStr(2)). */
    static String fNotes;

    private BatchRun() {
    }

    public static void main(String[] args) throws IOException {
        Properties p = new Properties();
        try (InputStream in = new FileInputStream(args.length > 0 ? args[0] : "etl.properties")) {
            p.load(in);
        }
        try {
            run(p);
        } finally {
            Db.close();   // a run that did not reach its commit is rolled back, as in the legacy
        }
    }

    /** Mirror of the LegacyEtl.pas program block. */
    static void run(Properties p) {
        // DefaultSystemCodePage := CP_UTF8: database text is UTF-8; Java strings are Unicode, nothing to set
        // Form := TMainForm.Create
        formCreate(p);
        buttonRunClick();
        // Form.Free
    }

    /** TMainForm.FormCreate. */
    static void formCreate(Properties p) {
        fDb = p.getProperty("jdbc.url");          // was ParamStr(1)
        fNotes = p.getProperty("notes.file");     // was ParamStr(2)
        Common.gSkipVoid = true;                  // business rule: zero-quantity orders are voided
        Db.open(p);                               // was OpenDb(FDb)
    }

    /** TMainForm.ButtonRunClick. */
    static void buttonRunClick() {
        Customer.runCustomerClean(fNotes);
        Orders.runOrderAmount();
        CitySum.runCitySum();
        Db.commit();                              // was CloseDb: GTrans.Commit; GConn.Close is Db.close in main
    }
}
