package etl.units;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.math.BigDecimal;
import org.junit.Test;

/** rule.md §5 / §6 behaviors. */
public class DelphiRtlTest {

    @Test
    public void roundIsHalfToEven() {
        assertEquals(2, DelphiRtl.round(new BigDecimal("2.5")));
        assertEquals(4, DelphiRtl.round(new BigDecimal("3.5")));
        assertEquals(-2, DelphiRtl.round(new BigDecimal("-2.5")));
    }

    @Test
    public void copyIsOneBasedAndClamped() {
        assertEquals("bc", DelphiRtl.copy("abc", 2, 10));
        assertEquals("", DelphiRtl.copy("abc", 5, 1));
        assertEquals(2, DelphiRtl.copy(new byte[] {1, 2, 3}, 2, 9).length);
    }

    @Test
    public void trimStripsOnlyControlAndSpace() {
        assertEquals("a ", DelphiRtl.trim("\t a  \n"));
    }

    @Test
    public void upperCaseIsAsciiOnly() {
        assertEquals("ZüRICH", DelphiRtl.upperCase("zürich"));
    }

    @Test
    public void strToIntDefGivesDefaultOnFailure() {
        assertEquals(0, DelphiRtl.strToIntDef("1a", 0));
        assertEquals(-7, DelphiRtl.strToIntDef("-7", 0));
        assertEquals(0, DelphiRtl.strToIntDef("", 0));
    }

    @Test
    public void dateSentinelsAndFormat() {
        assertEquals("19000101", DelphiRtl.formatDateTimeYyyymmdd(2.0));
        assertEquals("20220328", DelphiRtl.formatDateTimeYyyymmdd(44648.0));
        assertEquals(0.0, DelphiRtl.asFloat(null), 0.0);
    }

    @Test
    public void asCurrencyRoundsTheFloatToFourDecimals() {
        assertEquals(new BigDecimal("376.0750"), DelphiRtl.asCurrency(376.075));
        assertEquals(new BigDecimal("0.0000"), DelphiRtl.asCurrency(null));
    }

    @Test
    public void ansiCompareTextGivesTheC01CityOrder() {
        assertTrue(DelphiRtl.ansiCompareText("TAIPEI", "(UNKNOWN)") < 0);
        assertTrue(DelphiRtl.ansiCompareText("(UNKNOWN)", "ZüRICH") < 0);
        assertTrue(DelphiRtl.ansiCompareText("ZüRICH", "台南") < 0);
    }
}
