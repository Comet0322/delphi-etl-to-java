package etl.units;

import static org.junit.Assert.assertEquals;

import etl.core.Row;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.nio.file.Files;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

/** ETL-001. Expected values from the legacy output of C01 (T_CUST_CLEAN.csv) or rule.md. */
public class CustomerTest {

    private final UnitTestDb db = new UnitTestDb();
    private File notes;

    @Before
    public void setUp() throws Exception {
        db.open();
        db.exec("CREATE TABLE CUSTOMER (CUST_ID INTEGER, NAME TEXT, CITY TEXT, JOIN_DATE REAL)");
        notes = File.createTempFile("notes", ".txt");
    }

    @After
    public void tearDown() throws Exception {
        db.close();
        notes.delete();
    }

    private static byte[] bytes(Object... parts) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for (Object p : parts) {
            if (p instanceof String) {
                byte[] b = ((String) p).getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);
                out.write(b, 0, b.length);
            } else {
                for (int v : (int[]) p) {
                    out.write(v);
                }
            }
        }
        return out.toByteArray();
    }

    private Map<String, String> load(byte[] content) throws Exception {
        Files.write(notes.toPath(), content);
        Map<String, String> m = new LinkedHashMap<String, String>();
        Customer.loadNotes(notes.getAbsolutePath(), m);
        return m;
    }

    @Test
    public void rule001_idFromBytes1to4AndBig5NoteFromBytes5to24() throws Exception {
        // C01 cust_notes.txt line "   3" + Big5 b0 68 b3 66 a6 68 + spaces -> T_CUST_CLEAN id 3 NOTE 退貨多
        Map<String, String> m = load(bytes("   3", new int[] {0xb0, 0x68, 0xb3, 0x66, 0xa6, 0x68},
                "              \n   1pay late            \n"));
        assertEquals("退貨多", m.get("3"));
        assertEquals("pay late", m.get("1"));
    }

    @Test
    public void rule001_blankNoteRemovesTheIdAndShortLinesAreSkipped() throws Exception {
        // C01: customer 6 has a blank note line and gets NOTE ''
        Map<String, String> m = load(bytes("   6pay late\n   6                    \nabc\n"));
        assertEquals(null, m.get("6"));
        assertEquals(0, m.size());
    }

    @Test
    public void rule001_lastLineForAnIdWinsAndBadIdIsZero() throws Exception {
        Map<String, String> m = load(bytes("  12first\n  12second\n  x1third"));
        assertEquals("second", m.get("12"));
        assertEquals("third", m.get("0"));
    }

    @Test
    public void rule001_noteIsCutAt20BytesAndAHalfCharacterBecomesQuestionMark() throws Exception {
        // rule.md §6: a double-byte character cut by a byte-wise Copy becomes '?'
        Map<String, String> m = load(bytes("   7", "ABCDEFGHIJKLMNOPQRS", new int[] {0xb0, 0x68}, "\r\n"));
        assertEquals("ABCDEFGHIJKLMNOPQRS?", m.get("7"));
    }

    @Test
    public void rule005_rule006_rule001_cleanedRowsAsTheLegacyWroteThem() throws Exception {
        // C01 CUSTOMER rows and their legacy T_CUST_CLEAN rows
        db.exec("INSERT INTO CUSTOMER VALUES (1, '黃美玲       ', 'kaohsiung', 44648.0)");
        db.exec("INSERT INTO CUSTOMER VALUES (9, '黃美玲       ', 'zürich', 41320.0)");
        db.exec("INSERT INTO CUSTOMER VALUES (11, 'lin       ', 'Hsinchu', 0.0)");
        db.exec("INSERT INTO CUSTOMER VALUES (13, '李大華       ', 'Taichung', NULL)");
        db.exec("INSERT INTO CUSTOMER VALUES (6, 'chen      ', '  tainan ', 36957.0)");
        Files.write(notes.toPath(), bytes("   1pay late            \n"));
        Customer.runCustomerClean(notes.getAbsolutePath());
        List<Row> r = db.rows("SELECT * FROM T_CUST_CLEAN_NEW");
        assertEquals(5, r.size());
        assertRow(r.get(0), 1, "黃美玲", "KAOHSIUNG", "20220328", "pay late");
        assertRow(r.get(1), 6, "chen", "TAINAN", "20010307", "");
        assertRow(r.get(2), 9, "黃美玲", "ZüRICH", "20130215", "");
        assertRow(r.get(3), 11, "lin", "HSINCHU", "", "");
        assertRow(r.get(4), 13, "李大華", "TAICHUNG", "", "");
    }

    @Test
    public void implicit_nullTextAndIdBecomeEmptyAndZero() throws Exception {
        db.exec("INSERT INTO CUSTOMER VALUES (NULL, NULL, NULL, NULL)");
        Files.write(notes.toPath(), bytes("   0zero note\n"));
        Customer.runCustomerClean(notes.getAbsolutePath());
        assertRow(db.rows("SELECT * FROM T_CUST_CLEAN_NEW").get(0), 0, "", "", "", "zero note");
    }

    private static void assertRow(Row r, int id, String nm, String ct, String jd, String nt) {
        assertEquals(id, ((Number) r.get("CUST_ID")).intValue());
        assertEquals(nm, r.get("NAME"));
        assertEquals(ct, r.get("CITY"));
        assertEquals(jd, r.get("JOIN_DATE"));
        assertEquals(nt, r.get("NOTE"));
    }
}
