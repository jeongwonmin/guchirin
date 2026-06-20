# Guchirin (ぐちりん)

完全ローカルで動くLLMチャットアプリ。家族にも打ち明けられないこと、人生の悩み、なかなか人に理解してもらえない内密な悩み。安心して愚痴る場所としてご活用ください。
Ollama + FastAPI + 素のHTML/JS。

## 必要なもの
- [Ollama](https://ollama.com/) がインストール・起動済みであること
- Python 3.11（chromadbの依存ライブラリがWindowsでビルド不要なバージョン）

## セットアップ

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

ollama pull gemma3:4b-it-qat   # メインチャットモデル（未取得の場合）
ollama pull gemma3:1b          # memory判定・抽出用の軽量モデル
```

## 起動

```powershell
.venv\Scripts\activate
uvicorn backend.main:app --reload
```

ブラウザで http://localhost:8000 を開く。

## 機能
- **チャット**: 左サイドバーでセッションを管理（新規作成・切替・削除）。履歴はSQLite (`data/chat.db`) に保存
- **Web検索**: 「検索モード」チェックボックスONなら必ずDuckDuckGo検索を実行。OFFの場合はメインモデル(`gemma3:4b-it-qat`)がfunction callingで必要性を判断し、自律的に`web_search`ツールを呼び出す
- **Memory**: ユーザーの好み・事実を軽量LLM(`gemma3:1b`)が自動抽出してChromaDB (`data/chroma/`) に保存。応答生成時はメインモデルが`retrieve_memory`ツールを呼ぶか自律的に判断してベクトル検索で参照。右側の「記憶パネル」から一覧・追加・削除が可能。既定で1000件が上限で、9割を超えると警告、満杯になると新規追加は停止し既存記憶の更新のみ行われる

## 設定
`backend/config.py` でモデル名・容量上限などを変更できる。

## 今後の予定
AndroidはWebViewではなくネイティブアプリ（端末上でのオンデバイス推論）として別途実装予定。今回のAPI設計（`/chat`, `/sessions`, `/memory`）はその際の参考契約として扱う。
