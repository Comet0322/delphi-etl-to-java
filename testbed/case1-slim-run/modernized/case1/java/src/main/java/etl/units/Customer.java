package etl.units;

import etl.core.Db;
import etl.core.EtlException;
import etl.core.Row;
import etl.core.Tables;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** uCustomer.pas: clean customer master and attach free-text notes from a Big5 file. */
public final class Customer {

    private Customer() {
    }

    /**
     * LoadNotes. Notes file layout (Big5, one record per line): cols 1-4 customer id, right aligned; cols 5-24
     * note, padded with spaces to 20 bytes. {@code notes} is the TStringList Values store (name to value).
     */
    public static void loadNotes(String fileName, Map<String, String> notes) {
        List<byte[]> f;
        byte[] line;
        byte[] note;
        int id;
        String noteText;
        // ETL-001/OP-01
        f = readLines(fileName);                       // AssignFile / Reset
        try {
            for (byte[] l : f) {                       // while not Eof(F) ... ReadLn(F, Line)
                line = l;
                // ETL-001/OP-02
                if (DelphiRtl.length(line) < 5) {
                    continue;
                }
                // ETL-001/OP-03
                id = DelphiRtl.strToIntDef(DelphiRtl.trim(DelphiRtl.copy(line, 1, 4)), 0);
                // ETL-001/OP-04
                note = DelphiRtl.copy(line, 5, 20);
                noteText = DelphiRtl.decodeMs950(note);    // SetCodePage 950, then to CP_UTF8
                // ETL-001/OP-05
                valuesPut(notes, DelphiRtl.intToStr(id), DelphiRtl.trimRight(noteText));
            }
        } finally {
            // CloseFile(F)
        }
    }

    /** RunCustomerClean. */
    public static void runCustomerClean(String notesFile) {
        Map<String, String> notes;
        List<Row> q;
        int id;
        String nm;
        String ct;
        String jd;
        double d;
        notes = new LinkedHashMap<String, String>();
        try {
            // ETL-001/OP-01
            loadNotes(notesFile, notes);
            // ETL-001/OP-06
            Db.current().execute("DROP TABLE IF EXISTS " + Tables.out("T_CUST_CLEAN"));
            Db.current().execute("CREATE TABLE " + Tables.out("T_CUST_CLEAN")
                    + " (CUST_ID INTEGER, NAME TEXT, CITY TEXT, JOIN_DATE TEXT, NOTE TEXT)");
            // ETL-001/OP-07
            q = Db.current().query("SELECT CUST_ID, NAME, CITY, JOIN_DATE FROM CUSTOMER ORDER BY CUST_ID");
            for (Row r : q) {
                id = DelphiRtl.asInteger(r.get("CUST_ID"));
                nm = DelphiRtl.trim(DelphiRtl.asString(r.get("NAME")));
                ct = DelphiRtl.upperCase(DelphiRtl.trim(DelphiRtl.asString(r.get("CITY"))));
                // ETL-001/OP-08
                d = DelphiRtl.asFloat(r.get("JOIN_DATE"));
                if (d == 0) {
                    jd = "";
                } else {
                    jd = DelphiRtl.formatDateTimeYyyymmdd(d);
                }
                // ETL-001/OP-09
                Db.current().execute("INSERT INTO " + Tables.out("T_CUST_CLEAN") + " VALUES (?, ?, ?, ?, ?)",
                        id, nm, ct, jd, valuesGet(notes, DelphiRtl.intToStr(id)));
            }
        } finally {
            // Notes.Free
        }
    }

    /** TStringList.Values[k] := v: an empty value deletes the entry, otherwise replaces or appends it. */
    static void valuesPut(Map<String, String> list, String name, String value) {
        if (value.isEmpty()) {
            list.remove(name);
        } else {
            list.put(name, value);
        }
    }

    /** TStringList.Values[k]: '' when the name is absent. */
    static String valuesGet(Map<String, String> list, String name) {
        String v = list.get(name);
        return v == null ? "" : v;
    }

    /** ReadLn over a text file as bytes: a line ends at LF, CR LF or CR; a last line without end is read. */
    private static List<byte[]> readLines(String fileName) {
        byte[] all;
        try {
            all = Files.readAllBytes(Paths.get(fileName));
        } catch (IOException e) {
            throw new EtlException("cannot open " + fileName, e);
        }
        List<byte[]> lines = new ArrayList<byte[]>();
        ByteArrayOutputStream cur = new ByteArrayOutputStream();
        int i = 0;
        while (i < all.length) {
            byte b = all[i];
            if (b == '\n' || b == '\r') {
                lines.add(cur.toByteArray());
                cur.reset();
                if (b == '\r' && i + 1 < all.length && all[i + 1] == '\n') {
                    i++;
                }
            } else {
                cur.write(b);
            }
            i++;
        }
        if (cur.size() > 0) {
            lines.add(cur.toByteArray());
        }
        return lines;
    }
}
