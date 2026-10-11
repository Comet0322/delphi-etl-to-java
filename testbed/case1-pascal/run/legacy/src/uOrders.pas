unit uOrders;
{$mode delphi}

{ ETL: compute the payable amount of each order. }

interface

procedure RunOrderAmount;

implementation

uses
  SysUtils, sqldb, uCommon;

function CentsToStr(Cents: Int64): string;
var
  Sign: string;
begin
  Sign := '';
  if Cents < 0 then
  begin
    Sign := '-';
    Cents := -Cents;
  end;
  Result := Sign + IntToStr(Cents div 100) + '.' + Format('%.2d', [Cents mod 100]);
end;

procedure RunOrderAmount;
var
  Q, Ins: TSQLQuery;
  Qty, Disc: Integer;
  Price, Amt: Currency;
  Status: string;
begin
  ExecSql('DROP TABLE IF EXISTS T_ORDER_AMT');
  ExecSql('CREATE TABLE T_ORDER_AMT (ORDER_ID INTEGER, CUST_ID INTEGER, AMOUNT TEXT, NOTE TEXT, STATUS TEXT)');
  Q := NewQuery('SELECT ORDER_ID, CUST_ID, QTY, UNIT_PRICE, DISCOUNT_PCT, NOTE FROM ORDERS ORDER BY ORDER_ID');
  Ins := NewQuery('INSERT INTO T_ORDER_AMT VALUES (:id, :cid, :amt, :nt, :st)');
  Q.Open;
  while not Q.Eof do
  begin
    Qty := Q.FieldByName('QTY').AsInteger;
    if GSkipVoid and (Qty = 0) then
    begin
      Q.Next;
      Continue;
    end;
    Price := Q.FieldByName('UNIT_PRICE').AsCurrency;
    Disc := Q.FieldByName('DISCOUNT_PCT').AsInteger;
    Amt := Qty * Price;
    Amt := Amt - Amt * Disc / 100;
    if Disc > 10 then Status := 'S' else Status := 'N';
    Ins.Params.ParamByName('id').AsInteger := Q.FieldByName('ORDER_ID').AsInteger;
    Ins.Params.ParamByName('cid').AsInteger := Q.FieldByName('CUST_ID').AsInteger;
    Ins.Params.ParamByName('amt').AsString := CentsToStr(Round(Amt * 100));
    Ins.Params.ParamByName('nt').AsString := Q.FieldByName('NOTE').AsString;
    Ins.Params.ParamByName('st').AsString := Status;
    Ins.ExecSQL;
    Q.Next;
  end;
  Q.Free;
  Ins.Free;
end;

end.
