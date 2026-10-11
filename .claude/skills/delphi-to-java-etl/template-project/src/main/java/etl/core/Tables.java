package etl.core;

/**
 * The single place where the old/new table suffix is applied.
 * Jobs write outputs with {@code Tables.out("T_ORDER")}, never a bare name.
 */
public final class Tables {

    private static volatile String suffix = "_NEW";

    private Tables() {
    }

    public static void setSuffix(String value) {
        suffix = value == null ? "" : value;
    }

    public static String out(String table) {
        return table + suffix;
    }
}
