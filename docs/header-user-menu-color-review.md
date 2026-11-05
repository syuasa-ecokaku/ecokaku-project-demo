# 共通ヘッダー：ユーザーメニュー配色

開始点 `3f62375`、作業ブランチ `feat/light-header-user-menu`。開始時はリモートmainと一致し、追跡ファイルの未コミット変更・AGENTS.mdはなし。既存の未追跡 `.agents/` は保持する。

変更は `index.html` のiframe内CSSのみ。丸み、位置、写真、表示内容、クリック範囲、開閉処理、ヘッダーのグラデーションとロゴを維持した。

| 対象 | 配色・表示 |
| --- | --- |
| ボタン背景／枠線 | `#EAF6FF`／1px `#B9DFFF` |
| 氏名 | `#123B5D`、太字 |
| サブテキスト | `#526B80` |
| 下向き矢印 | `#123B5D` |
| 写真の外周 | 1px白アウトライン。写真のサイズを変更しない |
| ホバー／展開中 | `#D8EDFC` |
| キーボードフォーカス | 濃色の枠と白い外周リング。通常時の影はなし |
| UI REVIEW | 白14％の背景、白40％の枠、白文字。既存のサイズ・スマホでの非表示を維持 |

氏名・サブテキスト・矢印・写真のスタイルは `#account-toggle` 内または専用IDに限定し、ドロップダウン内の文字色に波及しない。

ChromiumでPC 1550px、スマホ390px・320pxを確認。指定色、通常／ホバー／展開中、フォーカス、Enter開閉、Esc、外側クリック、プロフィール遷移が成功。変更前との比較で写真・ヘッダーDOM・サイズ・クリック範囲・グラデーション・ロゴ・ドロップダウンの文字スタイルが一致した。全7部門と全社トップの本文HTML、アプリケーション処理も一致。検証5群成功、JavaScriptエラー・リソース失敗・外部書き込み0件。`git diff --check` も成功。

スクリーンショット：`/tmp/ecokaku-header-color-review/desktop-normal.png`、`desktop-expanded.png`、`mobile-normal.png`、`mobile-expanded.png`。確認スクリプトと結果は同環境の `/tmp/header-color-review.py`、`/tmp/ecokaku-header-color-review/results.json`。

mainへのマージ・本番公開は行わない。
