unit uCustomer;
{$mode delphi}

{ ETL: clean customer master and attach free-text notes from a Big5 file. }

interface

procedure RunCustomerClean(const NotesFile: string);

implementation

uses
  SysUtils, Classes, sqldb, cp950, uCommon;

{ Notes file layout (Big5, one record per line):
  cols 1-4  : customer id, right aligned
  cols 5-24 : note, padded with spaces to 20 bytes }
procedure LoadNotes(const FileName: string; Notes: TStringList);
var
  F: TextFile;
  Line, Note: RawByteString;
  Id: Integer;
begin
  AssignFile(F, FileName);
  Reset(F);
  try
    while not Eof(F) do
    begin
      ReadLn(F, Line);
      if Length(Line) < 5 then Continue;
      Id := StrToIntDef(Trim(Copy(Line, 1, 4)), 0);
      Note := Copy(Line, 5, 20);
      SetCodePage(Note, 950, False);
      SetCodePage(Note, CP_UTF8, True);
      Notes.Values[IntToStr(Id)] := TrimRight(Note);
    end;
  finally
    CloseFile(F);
  end;
end;

procedure RunCustomerClean(const NotesFile: string);
var
  Notes: TStringList;
  Q, Ins: TSQLQuery;
  Id: Integer;
  Nm, Ct, Jd: string;
  D: TDateTime;
begin
  Notes := TStringList.Create;
  try
    LoadNotes(NotesFile, Notes);
    ExecSql('DROP TABLE IF EXISTS T_CUST_CLEAN');
    ExecSql('CREATE TABLE T_CUST_CLEAN (CUST_ID INTEGER, NAME TEXT, CITY TEXT, JOIN_DATE TEXT, NOTE TEXT)');
    Q := NewQuery('SELECT CUST_ID, NAME, CITY, JOIN_DATE FROM CUSTOMER ORDER BY CUST_ID');
    Ins := NewQuery('INSERT INTO T_CUST_CLEAN VALUES (:id, :nm, :ct, :jd, :nt)');
    Q.Open;
    while not Q.Eof do
    begin
      Id := Q.FieldByName('CUST_ID').AsInteger;
      Nm := Trim(Q.FieldByName('NAME').AsString);
      Ct := UpperCase(Trim(Q.FieldByName('CITY').AsString));
      D := Q.FieldByName('JOIN_DATE').AsFloat;
      if D = 0 then
        Jd := ''
      else
        Jd := FormatDateTime('yyyymmdd', D);
      Ins.Params.ParamByName('id').AsInteger := Id;
      Ins.Params.ParamByName('nm').AsString := Nm;
      Ins.Params.ParamByName('ct').AsString := Ct;
      Ins.Params.ParamByName('jd').AsString := Jd;
      Ins.Params.ParamByName('nt').AsString := Notes.Values[IntToStr(Id)];
      Ins.ExecSQL;
      Q.Next;
    end;
    Q.Free;
    Ins.Free;
  finally
    Notes.Free;
  end;
end;

end.
