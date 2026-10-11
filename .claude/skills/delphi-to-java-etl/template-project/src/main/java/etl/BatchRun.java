package etl;

import etl.core.Db;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;

/**
 * Entry point and the one place that opens the database. It mirrors the legacy program's driver one to one:
 * the startup code (for a form-based tool, TMainForm.FormCreate) and the run (the button handler), calling the
 * migrated unit classes in etl.units in the legacy order. Set a breakpoint in {@link #run} to step through a
 * batch the way the Delphi IDE would.
 *
 * <p>Usage: {@code java -cp target/classes:target/lib/* etl.BatchRun etl.properties}. Command-line parameters
 * and ini settings the legacy read (ParamStr, TIniFile) are keys in etl.properties.
 *
 * <p>Replace the body of {@link #run} with the mirror of the legacy driver; keep {@link #main} as it is.
 */
public final class BatchRun {

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

    /** Mirror of the legacy driver. Example for a form whose button runs three units:
     * <pre>
     *   // TMainForm.FormCreate
     *   String notes = p.getProperty("notes.file");   // was ParamStr(2)
     *   Common.gSkipVoid = true;
     *   Db.open(p);                                  // was OpenDb(ParamStr(1))
     *   // TMainForm.ButtonRunClick
     *   Customer.runCustomerClean(notes);
     *   Orders.runOrderAmount();
     *   CitySum.runCitySum();
     *   Db.commit();                                 // was CloseDb: GTrans.Commit
     * </pre>
     */
    static void run(Properties p) {
        Db.open(p);
        Db.commit();
    }
}
