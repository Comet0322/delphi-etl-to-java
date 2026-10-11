unit uCommon;
{$mode delphi}

interface

uses
  SysUtils, Classes, sqldb, sqlite3conn;

var
  GConn: TSQLite3Connection;
  GTrans: TSQLTransaction;
  GSkipVoid: Boolean;   // set in TMainForm.FormCreate, read by the order ETL

procedure OpenDb(const Path: string);
procedure CloseDb;
procedure ExecSql(const S: string);
function NewQuery(const S: string): TSQLQuery;

implementation

procedure OpenDb(const Path: string);
begin
  GConn := TSQLite3Connection.Create(nil);
  GTrans := TSQLTransaction.Create(nil);
  GConn.DatabaseName := Path;
  GConn.Transaction := GTrans;
  GTrans.DataBase := GConn;
  GConn.Open;
end;

procedure CloseDb;
begin
  GTrans.Commit;
  GConn.Close;
end;

procedure ExecSql(const S: string);
begin
  GConn.ExecuteDirect(S);
end;

function NewQuery(const S: string): TSQLQuery;
begin
  Result := TSQLQuery.Create(nil);
  Result.DataBase := GConn;
  Result.Transaction := GTrans;
  Result.SQL.Text := S;
end;

end.
