package etl.units;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CharsetDecoder;
import java.nio.charset.CodingErrorAction;
import java.text.Collator;
import java.text.Normalizer;
import java.time.LocalDate;
import java.util.Comparator;
import java.util.Locale;

/**
 * Delphi / Free Pascal RTL routines used by the migrated units (rule.md §5, §6). One static method per routine,
 * with the legacy behavior for the values of the input domain.
 */
public final class DelphiRtl {

    /** TDateTime day 0. */
    private static final LocalDate DELPHI_EPOCH = LocalDate.of(1899, 12, 30);

    private DelphiRtl() {
    }

    // ---- rounding -------------------------------------------------------------------------------------------

    /** Round: half to even. */
    public static long round(BigDecimal x) {
        return x.setScale(0, RoundingMode.HALF_EVEN).longValueExact();
    }

    /** Round: half to even. */
    public static long round(double x) {
        return new BigDecimal(x).setScale(0, RoundingMode.HALF_EVEN).longValue();
    }

    /** Trunc: toward zero. */
    public static long trunc(double x) {
        return new BigDecimal(x).setScale(0, RoundingMode.DOWN).longValue();
    }

    // ---- Currency -------------------------------------------------------------------------------------------

    /** Currency value: scale 4, half to even. */
    public static BigDecimal curr(BigDecimal x) {
        return x.setScale(4, RoundingMode.HALF_EVEN);
    }

    /** StrToCurr: '.' decimal separator; raises on bad text as the legacy does. */
    public static BigDecimal strToCurr(String s) {
        try {
            return curr(new BigDecimal(trim(s)));
        } catch (NumberFormatException e) {
            throw new etl.core.EtlException("'" + s + "' is not a valid currency value", e);
        }
    }

    /** CurrToStrF(v, ffFixed, digits): fixed notation, no thousand separator, half away from zero. */
    public static String currToStrFFixed(BigDecimal v, int digits) {
        return v.setScale(digits, RoundingMode.HALF_UP).toPlainString();
    }

    // ---- strings --------------------------------------------------------------------------------------------

    /** Copy(s, i, n) on a String: 1-based, clamped, never throws. */
    public static String copy(String s, int index, int count) {
        int start = Math.max(index, 1) - 1;
        if (start >= s.length() || count <= 0) {
            return "";
        }
        int end = (int) Math.min((long) start + count, s.length());
        return s.substring(start, end);
    }

    /** Copy(s, i, n) on an ANSI byte string: 1-based, clamped, never throws. */
    public static byte[] copy(byte[] s, int index, int count) {
        int start = Math.max(index, 1) - 1;
        if (start >= s.length || count <= 0) {
            return new byte[0];
        }
        int end = (int) Math.min((long) start + count, s.length);
        byte[] r = new byte[end - start];
        System.arraycopy(s, start, r, 0, r.length);
        return r;
    }

    /** Pos(sub, s): 1-based, 0 when absent. */
    public static int pos(String sub, String s) {
        return s.indexOf(sub) + 1;
    }

    /** Length of a String: characters. */
    public static int length(String s) {
        return s.length();
    }

    /** Length of an ANSI byte string: bytes. */
    public static int length(byte[] s) {
        return s.length;
    }

    /** Trim: strips characters &lt;= #32 at both ends. */
    public static String trim(String s) {
        int b = 0;
        int e = s.length();
        while (b < e && s.charAt(b) <= ' ') {
            b++;
        }
        while (e > b && s.charAt(e - 1) <= ' ') {
            e--;
        }
        return s.substring(b, e);
    }

    /** TrimLeft: strips characters &lt;= #32 at the start. */
    public static String trimLeft(String s) {
        int b = 0;
        while (b < s.length() && s.charAt(b) <= ' ') {
            b++;
        }
        return s.substring(b);
    }

    /** TrimRight: strips characters &lt;= #32 at the end. */
    public static String trimRight(String s) {
        int e = s.length();
        while (e > 0 && s.charAt(e - 1) <= ' ') {
            e--;
        }
        return s.substring(0, e);
    }

    /** Trim on an ANSI byte string: strips bytes 0..32 at both ends. */
    public static byte[] trim(byte[] s) {
        int b = 0;
        int e = s.length;
        while (b < e && (s[b] & 0xFF) <= 32) {
            b++;
        }
        while (e > b && (s[e - 1] & 0xFF) <= 32) {
            e--;
        }
        return copy(s, b + 1, e - b);
    }

    /** UpperCase: ASCII letters only. */
    public static String upperCase(String s) {
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            sb.append(c >= 'a' && c <= 'z' ? (char) (c - 32) : c);
        }
        return sb.toString();
    }

    /** LowerCase: ASCII letters only. */
    public static String lowerCase(String s) {
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            sb.append(c >= 'A' && c <= 'Z' ? (char) (c + 32) : c);
        }
        return sb.toString();
    }

    /** AnsiUpperCase: full case mapping. */
    public static String ansiUpperCase(String s) {
        return s.toUpperCase(Locale.ROOT);
    }

    /** AnsiLowerCase: full case mapping. */
    public static String ansiLowerCase(String s) {
        return s.toLowerCase(Locale.ROOT);
    }

    /** StrToInt: decimal with optional sign, or '$' hexadecimal; raises on failure. */
    public static int strToInt(String s) {
        Integer v = parseInt(s);
        if (v == null) {
            throw new etl.core.EtlException("'" + s + "' is not a valid integer value");
        }
        return v.intValue();
    }

    /** StrToIntDef: the default on any parse failure. */
    public static int strToIntDef(String s, int def) {
        Integer v = parseInt(s);
        return v == null ? def : v.intValue();
    }

    /** StrToIntDef on an ANSI byte string (bytes outside ASCII never parse). */
    public static int strToIntDef(byte[] s, int def) {
        return strToIntDef(new String(s, java.nio.charset.StandardCharsets.ISO_8859_1), def);
    }

    private static Integer parseInt(String s) {
        if (s.isEmpty()) {
            return null;
        }
        int i = 0;
        boolean neg = false;
        if (s.charAt(0) == '-' || s.charAt(0) == '+') {
            neg = s.charAt(0) == '-';
            i = 1;
        }
        int radix = 10;
        if (i < s.length() && s.charAt(i) == '$') {
            radix = 16;
            i++;
        }
        if (i >= s.length()) {
            return null;
        }
        long v = 0;
        for (; i < s.length(); i++) {
            int d = Character.digit(s.charAt(i), radix);
            if (d < 0 || s.charAt(i) > 0x7F) {
                return null;
            }
            v = v * radix + d;
            if (v > 0x80000000L) {
                return null;
            }
        }
        v = neg ? -v : v;
        if (v > Integer.MAX_VALUE || v < Integer.MIN_VALUE) {
            return null;
        }
        return Integer.valueOf((int) v);
    }

    /** IntToStr. */
    public static String intToStr(long v) {
        return Long.toString(v);
    }

    /** Format('%.2d', [v]): at least two digits, zero padded. */
    public static String formatD2(long v) {
        String s = Long.toString(Math.abs(v));
        while (s.length() < 2) {
            s = "0" + s;
        }
        return v < 0 ? "-" + s : s;
    }

    /** FormatDateTime('yyyymmdd', d): the date part of a TDateTime (days since 1899-12-30). */
    public static String formatDateTimeYyyymmdd(double d) {
        LocalDate date = DELPHI_EPOCH.plusDays(trunc(d));
        return String.format("%04d%02d%02d", date.getYear(), date.getMonthValue(), date.getDayOfMonth());
    }

    // ---- field access (rule.md §6) --------------------------------------------------------------------------

    /** FieldByName(F).AsString: NULL gives ''. */
    public static String asString(Object v) {
        if (v == null) {
            return "";
        }
        if (v instanceof Double || v instanceof Float) {
            double d = ((Number) v).doubleValue();
            if (d == Math.rint(d) && Math.abs(d) < 1e15) {
                return Long.toString((long) d);
            }
            return Double.toString(d);
        }
        return v.toString();
    }

    /** FieldByName(F).AsInteger: NULL gives 0. */
    public static int asInteger(Object v) {
        if (v == null) {
            return 0;
        }
        if (v instanceof Number) {
            return ((Number) v).intValue();
        }
        return strToInt(trim(v.toString()));
    }

    /** FieldByName(F).AsFloat / AsDateTime: NULL gives 0.0. */
    public static double asFloat(Object v) {
        if (v == null) {
            return 0.0;
        }
        if (v instanceof Number) {
            return ((Number) v).doubleValue();
        }
        return Double.parseDouble(trim(v.toString()));
    }

    /** FieldByName(F).AsCurrency: NULL gives 0, the float value rounded to scale 4. */
    public static BigDecimal asCurrency(Object v) {
        if (v == null) {
            return BigDecimal.ZERO.setScale(4);
        }
        if (v instanceof Double || v instanceof Float) {
            return curr(new BigDecimal(((Number) v).doubleValue()));
        }
        return curr(new BigDecimal(v.toString()));
    }

    // ---- charset (rule.md §6) -------------------------------------------------------------------------------

    /** Big5 / CP950 bytes to text; an invalid or cut double-byte character becomes '?'. */
    public static String decodeMs950(byte[] bytes) {
        CharsetDecoder dec = Charset.forName("MS950").newDecoder()
                .onMalformedInput(CodingErrorAction.REPLACE)
                .onUnmappableCharacter(CodingErrorAction.REPLACE)
                .replaceWith("?");
        try {
            return dec.decode(ByteBuffer.wrap(bytes)).toString();
        } catch (CharacterCodingException e) {
            throw new etl.core.EtlException("cannot decode MS950", e);
        }
    }

    // ---- AnsiCompareText (sorted TStringList, CaseSensitive = False) ----------------------------------------

    private static final Collator PRIMARY = collator(Collator.PRIMARY);
    private static final Collator TERTIARY = collator(Collator.TERTIARY);

    private static Collator collator(int strength) {
        Collator c = Collator.getInstance(Locale.US);
        c.setStrength(strength);
        c.setDecomposition(Collator.CANONICAL_DECOMPOSITION);
        return c;
    }

    /**
     * AnsiCompareText as the legacy ran it (FPC cwstring: AnsiUpperCase both, then strcoll in en_US.UTF-8).
     * glibc's collation ignores punctuation and spaces at the first levels; this reproduces that order: letters
     * and digits compared primary (base letter), then with accents and case, then the full text by code point.
     * Equal (0) only for equal upper-cased text.
     */
    public static int ansiCompareText(String a, String b) {
        String ua = ansiUpperCase(a);
        String ub = ansiUpperCase(b);
        if (ua.equals(ub)) {
            return 0;
        }
        String fa = alnum(ua);
        String fb = alnum(ub);
        int c = PRIMARY.compare(fa, fb);
        if (c != 0) {
            return c;
        }
        c = TERTIARY.compare(fa, fb);
        if (c != 0) {
            return c;
        }
        c = ua.compareTo(ub);
        return c;
    }

    /** Comparator form of {@link #ansiCompareText}. */
    public static final Comparator<String> ANSI_COMPARE_TEXT = new Comparator<String>() {
        @Override
        public int compare(String a, String b) {
            return ansiCompareText(a, b);
        }
    };

    private static String alnum(String s) {
        String n = Normalizer.normalize(s, Normalizer.Form.NFC);
        StringBuilder sb = new StringBuilder(n.length());
        for (int i = 0; i < n.length(); i++) {
            char ch = n.charAt(i);
            if (Character.isLetterOrDigit(ch) || Character.isSurrogate(ch)) {
                sb.append(ch);
            }
        }
        return sb.toString();
    }
}
