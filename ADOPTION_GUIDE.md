# 公司導入指南

這份說明把 `code-modernization-delphi`（流程）和 `delphi-to-java-etl`（領域知識）帶到公司環境時，要調整什麼、怎麼使用。
原則：**流程（plugin）原則上不動，要改的是領域知識（skill）。**

## 1. 要帶過去的東西

| 路徑 | 是什麼 | 到公司後 |
|---|---|---|
| `plugins/code-modernization-delphi/` | 流程：router、各階段 agent、五支腳本 | 原則上不改 |
| `.claude/skills/delphi-to-java-etl/` | 領域知識：`SKILL.md`、`rule.md`、`template-project/` | 換成公司版本（第 3 節） |
| `testbed/` | case1 測試資料（Free Pascal 版的小型 ETL） | 用來確認環境相容性，之後可不用 |

## 2. 公司機器先確認的環境

| 項目 | 要確認的事 |
|---|---|
| Claude Code 2.0.30 | 這套從沒在 2.0.30 上跑過。要先實測：`--plugin-dir`、命令檔裡的 `${CLAUDE_PLUGIN_ROOT}`、用 `code-modernization-delphi:stage-analyze` 這種帶 plugin 前綴的名稱派 agent。2.0.30 的子 agent 不能再派子 agent，這套已經設計成只有一層，所以沒問題 |
| Python 3.7 以上 | 腳本只用標準函式庫 |
| git | router 每一步都會 commit |
| JDK 8、Maven | 要能連到公司的 Maven repository，或事先把依賴下載到本機快取 |
| 作業系統 | 如果是 Windows，`RUN.json` 的指令會由 cmd.exe 執行，SKILL.md 裡的指令要照這個寫。這點還沒驗證過 |

README 裡的 `--settings '{"advisorModel":""}'` 是新版 Claude Code 才需要的，2.0.30 可以拿掉。

## 3. 調整 skill（主要工作）

### SKILL.md：兩邊怎麼跑、怎麼取得輸出

- **輸入案例**：一個資料夾，每張輸入表一個 CSV，再加上程式會讀的其他檔案。
- **上傳下載工具**：寫一個小型 Java 命令列工具，包裝公司的 library，放在 skill 資料夾裡，提供兩個指令：
  - `upload <資料夾>`：每個 CSV 覆蓋測試庫裡對應的表。
  - `download <輸出資料夾> <表名,...> [--suffix _NEW]`：輸出格式和 `collect_sqlite.py` 相同（表頭、NULL 寫成 `\N`、文字加雙引號）。
- **舊程式那邊**：上傳輸入，執行 Delphi exe（寫清楚路徑、參數、怎麼指定測試庫），再下載 `T_X`。
- **新程式那邊**：上傳輸入，執行 BatchRun，再下載 `T_X_NEW`。舊程式可能改過輸入表，所以兩邊各上傳一次。
- **C01（範例輸入）怎麼取得**：把測試庫目前的輸入表下載成 CSV，當作 `--inputs`。
- **testbed 的內容**：fpc 和 `collect_sqlite.py` 是 case1 專用的，可以刪掉，或留著當範例。

### template-project

- `Db.open` 改成用公司的 library 連線，其他 `etl.core` 的類別盡量不動。
- `pom.xml` 加上公司的依賴。
- 改完先自己跑一次 `mvn package` 和測試。

### rule.md

| 節 | 要調整的內容 |
|---|---|
| §2 功能對照 | 列出公司舊程式實際用的連線元件、設定檔、記錄方式，各自對應到哪個 Java 方法 |
| §3 表名 | 如果是 Oracle，舊版本的識別名稱長度上限是 30 字元，加上 `_NEW` 可能超過，要訂規則 |
| §4 型別 | case1 用 SQLite，要改成 Oracle 的 NUMBER、DATE、VARCHAR2 對應 |
| §6 編碼 | 照資料庫實際的字元集調整 |
| §7 結構檢查 | 照公司的連線方式和套件結構調整 |
| §8 邊界案例類別 | 依公司資料的特性補充 |

### case1 產生的知識建議要先驗證

case1 跑出兩個建議：「`/` 以 80 位元 Extended 精度計算」和「FormatDateTime 先捨入到毫秒」。這兩個都是在 Linux 的 Free Pascal 上測出來的。

公司的 Delphi 如果編成 Win64，Extended 其實就是 double，結果可能正好相反。**要用公司的 Delphi 實測後，才寫進 rule.md。**

## 4. 資安和資料

- **RESULTS.json 含真實資料**：它存了兩邊的完整輸出，而且會被 commit 進工作資料夾的 git。如果測試資料有客戶個資，這個 git 不能推到共用的地方，或者要先確認測試資料可以這樣保存。
- **帳號密碼**：資料庫帳密不要寫進 `RUN.json`，用環境變數傳入。
- **測試庫只能一個人用**：執行期間會反覆覆蓋輸入表，其他人同時在用的話會互相干擾。

## 5. 使用方式

把原始碼和範例輸入設成唯讀：

```bash
chmod -R a-w <原始碼資料夾> <範例輸入資料夾>
```

在空的工作資料夾啟動 Claude Code：

```bash
mkdir work && cd work && claude --plugin-dir <路徑>/plugins/code-modernization-delphi
```

進入 Claude Code 後：

```
/code-modernization-delphi:modernize-auto <名稱> --source <原始碼> --inputs <範例輸入> --knowledge <skill 資料夾> --ask
```

| 參數 | 說明 |
|---|---|
| `--ask` | 轉換前停下來，問規則沒涵蓋的地方（自行假設的決策、rule.md 沒列的基礎設施呼叫）。不加則無人值守，所有假設列在 SUMMARY.md |
| `--one-stage` | 每做完一個階段就停，方便逐步檢查 |

headless（`claude -p`）沒辦法互動：加 `--ask` 時，問題會寫進 `analysis/<名稱>/STATUS.json` 後停下來，填好 `answer` 再重跑同一個命令。中途中斷時，重跑同一個命令也會從斷點接著做。

### 跑完看什麼

| 檔案 | 內容 |
|---|---|
| `analysis/<名稱>/SUMMARY.md` | 結果（PROVEN 或 NOT PROVEN）、每個 ETL 的狀態、自行假設的決策、audit 發現、知識建議、每一步的 commit |
| `git log` | 每個 agent 一個 commit；`git show <id>` 看某一步改了什麼 |
| `modernized/<名稱>/java/` | 轉換出的 Java 專案；在 `BatchRun.run` 設中斷點就能逐步除錯 |

## 6. 建議的導入順序

1. **確認相容性**：機器上有 Free Pascal 的話，先用 `testbed/case1` 確認 2.0.30 能跑完整個流程。
2. **準備領域知識**：完成第 3 節的上傳下載工具、模板連線、rule.md 調整。
3. **試點**：挑一支小程式，加 `--ask` 跑。你的回答會變成 rule.md 的修改建議。
4. **檢討**：看 SUMMARY.md，合併知識建議，檢查自行假設的決策和核心業務邏輯（`ANALYSIS.json` 的 `logic`，level 為 `core`）。
5. **擴大**：rule.md 夠完整之後，拿掉 `--ask`，無人值守跑其他程式。
