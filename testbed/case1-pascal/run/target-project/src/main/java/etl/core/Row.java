package etl.core;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;

/** One result row; column names are case-insensitive. SQL NULL is Java null. */
public final class Row {

    private final Map<String, Object> values = new LinkedHashMap<String, Object>();

    public void put(String column, Object value) {
        values.put(column.toUpperCase(), value);
    }

    public Object get(String column) {
        return values.get(column.toUpperCase());
    }

    public boolean isNull(String column) {
        return get(column) == null;
    }

    public String getString(String column) {
        Object v = get(column);
        return v == null ? null : v.toString();
    }

    public Integer getInt(String column) {
        Object v = get(column);
        return v == null ? null : Integer.valueOf(((Number) v).intValue());
    }

    public BigDecimal getDecimal(String column) {
        Object v = get(column);
        if (v == null) {
            return null;
        }
        return v instanceof BigDecimal ? (BigDecimal) v : new BigDecimal(v.toString());
    }

    public Map<String, Object> asMap() {
        return values;
    }
}
