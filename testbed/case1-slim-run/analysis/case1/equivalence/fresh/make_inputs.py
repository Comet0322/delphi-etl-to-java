#!/usr/bin/env python3
"""Deterministic fresh-input generator for case1 (standard library only).

Writes analysis/case1/equivalence/fresh/inputs/<Fnn>/{legacy.db,cust_notes.txt}, same structure as C01:
CUSTOMER(CUST_ID INTEGER, NAME TEXT, CITY TEXT, JOIN_DATE REAL), ORDERS(ORDER_ID, CUST_ID, ORDER_DATE REAL,
QTY INTEGER, UNIT_PRICE REAL, DISCOUNT_PCT INTEGER, NOTE TEXT), and a Big5 (cp950) notes file with 4-byte
right-aligned id + 20-byte note per line. Existing case folders are kept (never overwritten).

Input domain (DECISIONS D-004): UTF-8 database text, TDateTime 0..2958465, quantities and prices whose
Qty*Price*100 stays inside Currency, prices with at most 4 decimals, Big5 notes as the producer writes them.
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "inputs")

SCHEMA = [
    "CREATE TABLE CUSTOMER (CUST_ID INTEGER, NAME TEXT, CITY TEXT, JOIN_DATE REAL)",
    "CREATE TABLE ORDERS (ORDER_ID INTEGER, CUST_ID INTEGER, ORDER_DATE REAL,\n"
    "                     QTY INTEGER, UNIT_PRICE REAL, DISCOUNT_PCT INTEGER, NOTE TEXT)",
]


def note_line(cid, text, enc="cp950", pad=True):
    """4-byte right-aligned id + note bytes padded to 20 (no padding when pad=False)."""
    idb = cid if isinstance(cid, bytes) else str(cid).rjust(4).encode("ascii")
    nb = text if isinstance(text, bytes) else text.encode(enc)
    if pad and len(nb) < 20:
        nb = nb + b" " * (20 - len(nb))
    return idb + nb


def base_customers():
    return [(1, "Alice", "Taipei", 44000.0), (2, "Bob", "Tainan", 40000.0), (3, "黃美玲", "台南", 42000.0)]


def base_orders(start=1):
    return [(start, 1, 43001.0, 2, 10.5, 5, "a"), (start + 1, 2, 43002.0, 3, 7.25, 15, None),
            (start + 2, 3, 43003.0, 1, 99.99, 0, "")]


def base_notes():
    return [note_line(1, "pay late"), note_line(3, "VIP客戶")]


def cases():
    c = {}

    # F01 null_empty_zero
    c["F01"] = dict(
        customers=[(1, None, None, None), (2, "", "", 0.0), (3, "Zero", "Taipei", 0.0), (4, "Real", "Taipei", 44000.0),
                   (None, "NoId", "Tainan", 44001.0), (0, "IdZero", "Hsinchu", 44002.0)],
        orders=[(1, 1, 43001.0, None, 10.0, 5, None), (2, 2, 43002.0, 0, 10.0, 5, ""),
                (3, 3, 43003.0, 1, None, 5, "x"), (4, 4, 43004.0, 2, 10.0, None, None),
                (5, 4, 43005.0, 2, 0.0, 0, ""), (6, None, 43006.0, 1, 3.5, 0, None),
                (7, 0, None, 1, 4.5, 0, "zero cust"), (8, 4, 43008.0, 3, 1.0, 0, None),
                (None, 4, 43009.0, 1, 2.0, 0, "null id")],
        notes=[note_line(1, ""), note_line(2, "  "), note_line(4, "note four"), note_line(0, "zero id")],
    )

    # F02 thresholds (discount 9/10/11, 0, 100; qty 0, 1, -1)
    orders, oid = [], 1
    for qty in (-1, 0, 1, 2):
        for disc in (0, 9, 10, 11, 100):
            orders.append((oid, 1 + oid % 3, 43000.0 + oid, qty, 12.3456, disc, "t%d" % oid))
            oid += 1
    c["F02"] = dict(customers=base_customers(), orders=orders, notes=base_notes())

    # F03 rounding_ties: half-cent ties at Round(Amt*100) and half-unit ties at Currency scale 4
    orders, oid = [], 1
    prices = [0.005, 0.015, 0.025, 0.035, 0.045, 1.005, 2.675, 0.0050, 0.0150, 0.1250, 0.0001, 0.0003,
              1.2345, 0.0125, 2.5, 0.0005, 3.3333, 9.9995]
    for p in prices:
        for qty, disc in ((1, 0), (1, 50), (3, 10), (1, 5), (2, 25), (7, 15)):
            orders.append((oid, 1 + oid % 3, 43000.0, qty, p, disc, None))
            oid += 1
    c["F03"] = dict(customers=base_customers(), orders=orders, notes=base_notes())

    # F04 empty_table: both input tables empty, notes present
    c["F04"] = dict(customers=[], orders=[], notes=base_notes())

    # F05 empty_input_file: zero-byte notes file, data present
    c["F05"] = dict(customers=base_customers(), orders=base_orders(), notes=[], notes_raw=b"")

    # F06 duplicate_keys: CUSTOMER and ORDERS duplicate ids; notes repeat an id (last wins, empty deletes)
    c["F06"] = dict(
        customers=[(1, "First", "Taipei", 44000.0), (1, "Second", "Tainan", 44001.0), (2, "Two", "Hsinchu", 44002.0),
                   (2, "TwoB", "Hsinchu", 44003.0), (3, "Three", "Taichung", 44004.0)],
        orders=[(1, 1, 43001.0, 1, 5.0, 0, "a"), (1, 2, 43001.0, 2, 6.0, 0, "b"), (2, 3, 43002.0, 1, 7.0, 0, "c"),
                (2, 3, 43002.0, 1, 7.0, 0, "c"), (3, 1, 43003.0, 4, 1.25, 12, None)],
        notes=[note_line(1, "first"), note_line(1, "second"), note_line(2, "two"), note_line(2, ""),
               note_line(3, "three"), note_line(b"0003", "three again"), note_line(b"  03", "three last")],
    )

    # F07 missing_parent + city bucket case quirks
    c["F07"] = dict(
        customers=[(1, "A", "zürich", 44000.0), (2, "B", "ZÜRICH", 44000.0), (3, "C", "Zürich", 44000.0),
                   (4, "D", "", 44000.0), (5, "E", "(unknown)", 44000.0), (6, "F", "taipei", 44000.0),
                   (7, "G", "TAIPEI", 44000.0), (8, "H", None, 44000.0)],
        orders=[(i, cid, 43000.0, 1, 10.0 + i, 0, None) for i, cid in
                enumerate([1, 2, 3, 4, 5, 6, 7, 8, 99, 100, 99, 1, 2, -5], start=1)],
        notes=[note_line(99, "orphan note"), note_line(1, "zurich")],
    )

    # F08 large_values
    c["F08"] = dict(
        customers=[(2147483647, "Max" * 30, "Kaohsiung", 2958465.0), (1, "Big", "Kaohsiung", 2958465.5),
                   (2, "Mid", "Tainan", 100000.0)],
        orders=[(2147483647, 2147483647, 43000.0, 1000000, 99999.99, 0, "max"),
                (2, 1, 43000.0, 999999, 99999.9999, 3, None),
                (3, 2, 43000.0, 2147483647, 0.01, 11, None),
                (4, 2, 43000.0, 123456, 4321.0987, 20, "x" * 500)],
        notes=[note_line(9999, "max id"), note_line(2, "big")],
    )

    # F09 date_sentinels: TDateTime 0, NULL, 1900-01-01 (=2.0), and neighbours
    dates = [0.0, None, 2.0, 1.0, 0.0001, 0.5, 1.5, 3.0, 60.0, 61.0, 367.0, 25569.0, 36526.0, 44648.999,
             2958465.0]
    c["F09"] = dict(
        customers=[(i + 1, "D%d" % i, "Taipei", d) for i, d in enumerate(dates)],
        orders=[(i + 1, i + 1, d, 1, 2.0, 0, None) for i, d in enumerate(dates)],
        notes=base_notes(),
    )

    # F10 char_spaces
    c["F10"] = dict(
        customers=[(1, "  lead", "  taipei", 44000.0), (2, "trail  ", "tainan  ", 44000.0),
                   (3, "     ", "     ", 44000.0), (4, " \t both \t ", "\t hsinchu \t", 44000.0),
                   (5, " nbsp ", " taipei", 44000.0), (6, " 黃 ", " 台南 ", 44000.0)],
        orders=[(i, i, 43000.0, 1, 1.0, 0, n) for i, n in
                enumerate(["  lead", "trail  ", "   ", " both ", " ", " x "], start=1)],
        notes=[note_line(1, "  leading"), note_line(2, "trailing"), note_line(3, "                    "),
               note_line(b"   4", "   "), note_line(b"5   ", "id left aligned"), note_line(b" 6  ", "id centred")],
    )

    # F11 charset_bytes: Big5 note crossing the 20-byte Copy boundary, a double-byte char cut in half
    long_zh = "請電話聯絡客戶地址變更"            # 11 chars = 22 bytes: byte 20 is a lead byte
    odd = "A" + "請電話聯絡客戶地址變"           # 1 + 20 bytes: last char cut after its lead byte
    c["F11"] = dict(
        customers=[(i, "N%d" % i, "Taipei", 44000.0) for i in range(1, 11)],
        orders=base_orders(),
        notes=[note_line(1, long_zh), note_line(2, odd), note_line(3, "許功蓋"), note_line(4, "碁銹裏"),
               note_line(5, "ab請電話聯絡客戶地址變更"), note_line(6, "請電話聯絡客戶地址變"),
               note_line(7, "請", pad=False), note_line(8, b"x", pad=False), note_line(9, "VIP客戶" * 3),
               note_line(10, "中文English混合文字測試")],
    )

    # F12 notes file shapes: CRLF line ends, blank and short lines, non-numeric ids, no final newline
    lines = [note_line(1, "crlf one"), b"", b"abc", b"   ", note_line(b"ABCD", "letters id"),
             note_line(b"  2 ", "two"), note_line(b"   3", "三號客戶"), note_line(b"  -4", "minus")]
    c["F12"] = dict(customers=base_customers() + [(4, "Four", "Taichung", 44000.0)], orders=base_orders(),
                    notes=[], notes_raw=b"\r\n".join(lines) + b"\r\n" + note_line(4, "last no eol"))

    # F13 mixed city order: punctuation, accents and CJK in the sorted city bucket list
    cities = ["New York", "new-york", "Newark", "St. Louis", "Saint Louis", "O'Hare", "Århus", "Arhus", "Aarhus",
              "台北", "台南", "高雄", "123", "a1", "A-1", "Zürich", "Zurich", "  ", "Ünye", "Uppsala"]
    c["F13"] = dict(
        customers=[(i + 1, "C%d" % i, ct, 44000.0) for i, ct in enumerate(cities)],
        orders=[(i + 1, (i % len(cities)) + 1, 43000.0, 1 + i % 4, 3.3333, (i * 7) % 21, None)
                for i in range(60)] + [(61, 999, 43000.0, 1, 1.0, 0, None)],
        notes=base_notes(),
    )
    return c


def write_case(cid, spec):
    d = os.path.join(OUT, cid)
    if os.path.exists(d):
        return False
    os.makedirs(d)
    con = sqlite3.connect(os.path.join(d, "legacy.db"))
    for s in SCHEMA:
        con.execute(s)
    con.executemany("INSERT INTO CUSTOMER VALUES (?,?,?,?)", spec["customers"])
    con.executemany("INSERT INTO ORDERS VALUES (?,?,?,?,?,?,?)", spec["orders"])
    con.commit()
    con.close()
    raw = spec.get("notes_raw")
    if raw is None:
        raw = b"".join(l + b"\n" for l in spec["notes"])
    with open(os.path.join(d, "cust_notes.txt"), "wb") as fh:
        fh.write(raw)
    return True


def main():
    made = [cid for cid, spec in sorted(cases().items()) if write_case(cid, spec)]
    sys.stdout.write("made: %s\n" % (", ".join(made) or "none (all kept)"))


if __name__ == "__main__":
    main()
