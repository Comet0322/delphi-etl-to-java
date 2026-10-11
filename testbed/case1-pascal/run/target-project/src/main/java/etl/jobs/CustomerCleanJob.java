package etl.jobs;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import etl.core.DataAccess;
import etl.core.EtlException;
import etl.core.EtlJob;
import etl.core.Row;
import etl.core.Tables;

/** ETL-001 CustomerClean (legacy: uCustomer.pas RunCustomerClean / LoadNotes). */
public class CustomerCleanJob implements EtlJob {

    private static final Charset CP950 = Charset.forName("MS950");
    private static final LocalDate DELPHI_EPOCH = LocalDate.of(1899, 12, 30);
    private static final DateTimeFormatter YYYYMMDD = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final String notesFile;

    public CustomerCleanJob(String notesFile) {
        this.notesFile = notesFile;
    }

    @Override
    public String id() {
        return "ETL-001";
    }

    @Override
    public void run(DataAccess da) {
        Map<Integer, String> notes = loadNotes();                       // ETL-001/OP-01

        String table = Tables.out("T_CUST_CLEAN");                      // ETL-001/OP-07
        da.execute("DROP TABLE IF EXISTS " + table);
        da.execute("CREATE TABLE " + table
                + " (CUST_ID INTEGER, NAME TEXT, CITY TEXT, JOIN_DATE TEXT, NOTE TEXT)");

        List<Object[]> out = new ArrayList<Object[]>();
        for (Row r : da.query("SELECT CUST_ID, NAME, CITY, JOIN_DATE FROM CUSTOMER ORDER BY CUST_ID")) { // OP-02
            int id = r.getInt("CUST_ID") == null ? 0 : r.getInt("CUST_ID");
            String name = trim(r.getString("NAME"));                    // ETL-001/OP-03
            String city = upperAscii(trim(r.getString("CITY")));        // ETL-001/OP-04
            double d = r.isNull("JOIN_DATE") ? 0 : ((Number) r.get("JOIN_DATE")).doubleValue();
            String joinDate = d == 0 ? ""                               // ETL-001/OP-05
                    : DELPHI_EPOCH.plusDays((long) Math.floor(d)).format(YYYYMMDD);
            String note = notes.containsKey(id) ? notes.get(id) : "";   // ETL-001/OP-06
            out.add(new Object[] {id, name, city, joinDate, note});
        }
        da.insertBatch(table, Arrays.asList("CUST_ID", "NAME", "CITY", "JOIN_DATE", "NOTE"), out);
    }

    /** Bytes 1-4 id, bytes 5-24 Big5 note; short lines skipped; last duplicate wins. */
    private Map<Integer, String> loadNotes() {
        Map<Integer, String> map = new HashMap<Integer, String>();
        byte[] all;
        try {
            all = Files.readAllBytes(Paths.get(notesFile));
        } catch (IOException e) {
            throw new EtlException("cannot read notes file " + notesFile, e);
        }
        ByteArrayOutputStream line = new ByteArrayOutputStream();
        for (int i = 0; i <= all.length; i++) {
            if (i == all.length || all[i] == '\n') {
                if (i < all.length || line.size() > 0) {
                    addNote(map, line.toByteArray());
                }
                line.reset();
            } else if (all[i] != '\r') {
                line.write(all[i]);
            }
        }
        return map;
    }

    private void addNote(Map<Integer, String> map, byte[] line) {
        if (line.length < 5) {
            return;
        }
        String idText = trim(new String(line, 0, 4, Charset.forName("ISO-8859-1")));
        int id;
        try {
            id = Integer.parseInt(idText);
        } catch (NumberFormatException e) {
            id = 0;
        }
        int end = Math.min(line.length, 24);
        String note = new String(line, 4, end - 4, CP950);
        map.put(id, trimRight(note));
    }

    /** Delphi Trim: removes characters <= #32 on both sides. */
    private static String trim(String s) {
        return trimRight(trimLeft(s));
    }

    private static String trimLeft(String s) {
        if (s == null) {
            return "";
        }
        int i = 0;
        while (i < s.length() && s.charAt(i) <= ' ') {
            i++;
        }
        return s.substring(i);
    }

    private static String trimRight(String s) {
        if (s == null) {
            return "";
        }
        int i = s.length();
        while (i > 0 && s.charAt(i - 1) <= ' ') {
            i--;
        }
        return s.substring(0, i);
    }

    /** Delphi UpperCase on an ANSI string: only a-z are converted. */
    private static String upperAscii(String s) {
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            sb.append(c >= 'a' && c <= 'z' ? (char) (c - 32) : c);
        }
        return sb.toString();
    }
}
