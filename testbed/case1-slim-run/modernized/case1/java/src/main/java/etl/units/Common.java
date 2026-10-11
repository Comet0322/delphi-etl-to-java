package etl.units;

/**
 * uCommon.pas. OpenDb, CloseDb, ExecSql and NewQuery are infrastructure and replaced (rule.md §2): BatchRun calls
 * Db.open / Db.commit, units call Db.current(). GConn and GTrans only held the connection and transaction and
 * disappear.
 */
public final class Common {

    /** GSkipVoid: set in TMainForm.FormCreate, read by the order ETL. */
    public static boolean gSkipVoid;

    private Common() {
    }
}
