# Business rules - case1

### RULE-001: Notes attached to customers from the Big5 file
**ETL:** ETL-001
**Priority:** P0
**Confidence:** High
**Source:** uCustomer.pas:18-40
**Plain English:** Each notes line of at least 5 bytes gives customer id = bytes 1-4 (trimmed, 0 when not numeric) and note = bytes 5-24 decoded from Big5, right-trimmed; the last line for an id wins, and an empty note removes the id's note.

### RULE-002: Zero-quantity orders are voided
**ETL:** ETL-002
**Priority:** P0
**Confidence:** High
**Source:** uOrders.pas:43-47
**Plain English:** While GSkipVoid is True (always, set at startup), an order with QTY 0 or NULL is not written to T_ORDER_AMT.

### RULE-003: Payable order amount
**ETL:** ETL-002
**Priority:** P0
**Confidence:** High
**Source:** uOrders.pas:15-26,48-55
**Plain English:** Amount = Qty*UnitPrice minus that amount times DiscountPct/100 in Currency, rounded half-to-even to whole cents and written as text with exactly two decimals.

### RULE-004: Discount status flag
**ETL:** ETL-002
**Priority:** P1
**Confidence:** High
**Source:** uOrders.pas:52
**Plain English:** Status is 'S' when DISCOUNT_PCT is greater than 10, otherwise 'N'.

### RULE-005: Customer name and city cleaning
**ETL:** ETL-001
**Priority:** P1
**Confidence:** High
**Source:** uCustomer.pas:61-62
**Plain English:** Name is trimmed; city is trimmed and upper-cased for ASCII letters only; NULL becomes ''.

### RULE-006: Join date formatting
**ETL:** ETL-001
**Priority:** P1
**Confidence:** High
**Source:** uCustomer.pas:63-67
**Plain English:** JOIN_DATE 0 or NULL becomes '', any other value is formatted as yyyymmdd from the TDateTime day count.

### RULE-007: Order count and total per city
**ETL:** ETL-003
**Priority:** P0
**Confidence:** High
**Source:** uCitySum.pas:44-74
**Plain English:** Orders are grouped by their customer's cleaned city, with count and the Currency sum of AMOUNT, written with two decimals in sorted city order.

### RULE-008: Unknown city bucket
**ETL:** ETL-003
**Priority:** P1
**Confidence:** High
**Source:** uCitySum.pas:50-51
**Plain English:** An order whose customer is missing from T_CUST_CLEAN or has an empty city is counted under '(UNKNOWN)'.

### RULE-009: City total text format
**ETL:** ETL-003
**Priority:** P2
**Confidence:** Medium
**Source:** uCitySum.pas:74
**Plain English:** The city total is written as fixed text with 2 decimals (CurrToStrF ffFixed 2).
