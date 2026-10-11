unit uCitySum;
{$mode delphi}

{ ETL: order count and total amount per customer city.
  Depends on the outputs of uCustomer and uOrders. }

interface

procedure RunCitySum;

implementation

uses
  SysUtils, Classes, sqldb, uCommon;

type
  TCityAcc = class
    Cnt: Integer;
    Total: Currency;
  end;

procedure RunCitySum;
var
  CityOf: TStringList;
  Acc: TStringList;
  Q, Ins: TSQLQuery;
  City: string;
  Idx: Integer;
  A: TCityAcc;
  I: Integer;
begin
  CityOf := TStringList.Create;
  Acc := TStringList.Create;
  try
    Q := NewQuery('SELECT CUST_ID, CITY FROM T_CUST_CLEAN');
    Q.Open;
    while not Q.Eof do
    begin
      CityOf.Values[Q.FieldByName('CUST_ID').AsString] := Q.FieldByName('CITY').AsString;
      Q.Next;
    end;
    Q.Free;

    Acc.Sorted := True;
    Acc.Duplicates := dupIgnore;
    Q := NewQuery('SELECT CUST_ID, AMOUNT FROM T_ORDER_AMT');
    Q.Open;
    while not Q.Eof do
    begin
      City := CityOf.Values[Q.FieldByName('CUST_ID').AsString];
      if City = '' then City := '(UNKNOWN)';
      Idx := Acc.IndexOf(City);
      if Idx < 0 then
      begin
        A := TCityAcc.Create;
        Acc.AddObject(City, A);
      end
      else
        A := TCityAcc(Acc.Objects[Idx]);
      Inc(A.Cnt);
      A.Total := A.Total + StrToCurr(Q.FieldByName('AMOUNT').AsString);
      Q.Next;
    end;
    Q.Free;

    ExecSql('DROP TABLE IF EXISTS T_CITY_SUM');
    ExecSql('CREATE TABLE T_CITY_SUM (CITY TEXT, ORDER_CNT INTEGER, TOTAL TEXT)');
    Ins := NewQuery('INSERT INTO T_CITY_SUM VALUES (:c, :n, :t)');
    for I := 0 to Acc.Count - 1 do
    begin
      A := TCityAcc(Acc.Objects[I]);
      Ins.Params.ParamByName('c').AsString := Acc[I];
      Ins.Params.ParamByName('n').AsInteger := A.Cnt;
      Ins.Params.ParamByName('t').AsString := CurrToStrF(A.Total, ffFixed, 2);
      Ins.ExecSQL;
      A.Free;
    end;
    Ins.Free;
  finally
    Acc.Free;
    CityOf.Free;
  end;
end;

end.
