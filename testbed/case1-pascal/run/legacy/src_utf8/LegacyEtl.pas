program LegacyEtl;
{$mode delphi}

{ Stand-in for a form-based Delphi ETL tool: the work is wired to form events.
  Usage: LegacyEtl <sqlite db> <notes file (Big5)> }

uses
  {$ifdef unix}cwstring,{$endif}
  SysUtils, uCommon, uCustomer, uOrders, uCitySum;

type
  TMainForm = class
  private
    FDb, FNotes: string;
  public
    procedure FormCreate;
    procedure ButtonRunClick;
  end;

procedure TMainForm.FormCreate;
begin
  FDb := ParamStr(1);
  FNotes := ParamStr(2);
  GSkipVoid := True;    // business rule: zero-quantity orders are voided
  OpenDb(FDb);
end;

procedure TMainForm.ButtonRunClick;
begin
  RunCustomerClean(FNotes);
  RunOrderAmount;
  RunCitySum;
  CloseDb;
end;

var
  Form: TMainForm;
begin
  DefaultSystemCodePage := CP_UTF8;   // database text is UTF-8; Big5 only in the notes file
  Form := TMainForm.Create;
  Form.FormCreate;
  Form.ButtonRunClick;
  Form.Free;
end.
