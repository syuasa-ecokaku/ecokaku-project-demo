# 電力申請：3事業の独立画面

## 今回の変更

`index.html` の iframe 内の電力申請から「全事業」タブと専用UIを削除。

- 事業タブ：蓄電池・太陽光・データセンターの3つを左詰めで表示。
- 既存Lucide SVG、淡い青背景・濃い青文字／アイコン・3px下線・余白・モバイル横スクロールを維持。
- 業務タブ：サマリー・データ入力・案件詳細（summary／bulk／detail）を維持。
- 初期状態は `business: 'battery'`、`tab: 'summary'`。
- 左メニュー「電力申請」をクリックすると、表示だけを蓄電池・サマリーに戻す。下書き、検索条件、工程選択、選択案件、開閉状態は削除しない。
- 事業タブの切替では、選択中の業務タブを維持。太陽光・データセンターは引き続き準備中の表示のみ。

## 削除したUI・処理

全事業のKPI、事業別進捗一覧、全事業案件一覧、横断の共通データ入力・案件詳細への入口、全事業の説明文、専用CSSを削除した。

専用処理 `powerRegisteredBusinesses`、`powerBusinessMetrics`、`powerCrossCounts`、`powerCrossTable`、`powerCrossSummaryHTML`、`powerCommonDraftCount`、`powerCommonBulkHTML`、`powerSaveCommon` と、その描画・保存分岐を削除。事業タブに `all` を列挙・選択する処理は残していない。

`powerSaveBar` の `all` スコープは、蓄電池の全案件の下書きを保存・取消するための共通処理なので維持する。「全事業」の選択状態とは異なる。

## 保持したデータ・機能

サンプル案件、案件番号、工程番号、項目定義、事業別ストア、事業別設定、案件の事業所属配列は変更していない。旧サンプルの名称や設備区分も変更していない。

蓄電池の個別KPI・検索・絞り込み・並べ替え・データ入力・案件詳細・下書き・保存・取消・添付名・タスク・履歴・番号照合・連系見込・再接続検討を保持。既存の担当者・対応状態・共通対応期限は蓄電池の入力項目として残す。

変更前との比較で `powerSchemas`、`powerBusinessStores`、`powerBusinessConfigs` と、`powerRecord`、`powerSummaryHTML`、`powerBulkHTML`、`powerDetailHTML`、`powerSave`、`powerCancel`、`powerIssues`、`showPage` が同一であることを確認。営業・法務の実装も変更していない。共通クリック処理の変更は電力申請メニューの初期表示設定のみ。

## 拡張箇所

実表示は `iframe[data-srcdoc]` 内。事業ごとの `powerBusinessConfigs` と `powerBusinessStores` を引き続き使用する。太陽光・データセンターの項目・工程は未確定なので追加していない。将来は確定した定義・描画／保存処理を各事業へ実装し、蓄電池のデータや同番号の工程と混在させない。

## ブラウザー検証

- `python3 tests/power_mock_smoke.py`：既存の14グループ成功。
- `python3 tests/power_business_smoke.py`：今回の6グループ成功。
- 合計20グループ。未処理JavaScript例外、外部リソース取得失敗、書き込み／アップロード通信は0件。
- 全事業UIが全3事業・業務タブで表示されないこと、蓄電池・サマリーの初期表示、メニュー再入、事業切替時の業務タブ維持、SVG・配色・モバイル表示を確認。
- 検索条件・下書きの保持、保存・取消、案件間のデータ／添付名／タスク分離と、営業・法務・設定の主要操作を確認。
- 構文チェック、`git diff --check` 成功。

結果と画面：`/tmp/ecokaku-power-three-review/`（既存回帰）、`/tmp/ecokaku-power-business-review/`（今回の3事業確認）。

保存範囲は従来と同じ画面内メモリのみ。再読み込みで初期化し、ファイル本体のアップロード・サーバー保存・外部連携は行わない。
