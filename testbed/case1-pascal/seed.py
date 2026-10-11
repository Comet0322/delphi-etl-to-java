#!/usr/bin/env python3
"""Create the input data of test case 1 (deterministic).

Writes legacy/data/legacy.db (CUSTOMER, ORDERS) and legacy/data/cust_notes.txt
(Big5 fixed width). Deliberate traps: padded CHAR names (some with leading
spaces), TDateTime 0 / NULL join dates, Chinese text in a Big5 file, a
non-ASCII city, exact half-cent ties, NULL notes, zero-quantity orders,
orders of unknown customers.
"""
import os
import random
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "legacy", "data")
os.makedirs(DATA, exist_ok=True)
db_path = os.path.join(DATA, "legacy.db")
if os.path.exists(db_path):
    os.remove(db_path)

rnd = random.Random(20261011)
cities = ["taipei", "Taichung", "kaohsiung", "台南", "zürich", "Hsinchu", "  tainan "]
names = ["alice", "BOB", "chen", "王小明", "李大華", "Wang", "lin", "黃美玲", "zhang", "Wu"]
notes = ["VIP客戶", "", "請電話聯絡", "pay late", "新客戶", "地址變更", "", "退貨多"]

con = sqlite3.connect(db_path)
con.executescript("""
CREATE TABLE CUSTOMER (CUST_ID INTEGER, NAME TEXT, CITY TEXT, JOIN_DATE REAL);
CREATE TABLE ORDERS (ORDER_ID INTEGER, CUST_ID INTEGER, ORDER_DATE REAL,
                     QTY INTEGER, UNIT_PRICE REAL, DISCOUNT_PCT INTEGER, NOTE TEXT);
""")

N_CUST, N_ORD = 120, 600
for cid in range(1, N_CUST + 1):
    name = rnd.choice(names)
    name = (" " + name if cid % 17 == 0 else name).ljust(10)          # CHAR(10) padding
    city = rnd.choice(cities)
    if cid % 11 == 0:
        jd = 0.0                                                        # empty-date sentinel
    elif cid % 13 == 0:
        jd = None                                                       # NULL
    else:
        jd = float(36526 + rnd.randint(0, 9000))                        # 2000-01-01 + n days
    con.execute("INSERT INTO CUSTOMER VALUES (?,?,?,?)", (cid, name, city, jd))

ties = [0.125, 0.375, 2.5, 12.345, 19.995, 0.005]
for oid in range(1, N_ORD + 1):
    cid = rnd.randint(1, N_CUST) if oid % 50 else N_CUST + 5             # some unknown customers
    qty = rnd.choice([0, 1, 2, 3, 5, 10, 24]) if oid % 7 else 0
    price = rnd.choice(ties) if oid % 3 == 0 else round(rnd.uniform(1, 500), 3)
    disc = rnd.choice([0, 0, 5, 10, 12, 15, 20])
    note = rnd.choice([None, None, "rush", "gift", ""])
    con.execute("INSERT INTO ORDERS VALUES (?,?,?,?,?,?,?)",
                (oid, cid, float(43000 + oid), qty, price, disc, note))
con.commit()
con.close()

# Big5 fixed width: 4-char id + 20-byte note (space padded). Lines end with LF.
with open(os.path.join(DATA, "cust_notes.txt"), "wb") as f:
    for cid in range(1, N_CUST + 1):
        if cid % 9 == 0:
            continue                                                    # customer without a note
        raw = rnd.choice(notes).encode("cp950")[:20]
        f.write(("%4d" % cid).encode("ascii") + raw.ljust(20, b" ") + b"\n")
print("seeded", db_path)
