"""Ollama(ローカルLLM)による商談議事録の解析"""
from __future__ import annotations

import json
import os
import re

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")

SYSTEM_PROMPT = """
あなたは商談議事録を分析する専門AIです。
以下のJSON形式のみで回答してください。余分なテキストは不要です。

{
  "summary": "商談の概要(3文以内)",
  "client_name": "クライアント名(不明な場合は「不明」)",
  "meeting_date": "商談日(テキストから推測、不明なら今日の日付)",
  "problems": [
    {"title": "問題タイトル", "detail": "詳細説明", "priority": "高/中/低"}
  ],
  "tasks": [
    {"task": "タスク内容", "owner": "担当者名", "deadline": "期限", "status": "未完了"}
  ],
  "documents_needed": [
    {"doc_name": "書類名", "purpose": "用途", "template_hint": "記載すべき内容のヒント"}
  ],
  "estimate": {
    "items": [
      {"name": "項目名", "detail": "説明", "amount": 金額数値, "unit": "円"}
    ],
    "total": 合計金額数値,
    "notes": "備考・条件"
  },
  "slides": [
    {"title": "スライドタイトル", "content": "本文(箇条書き可)", "type": "cover/problem/solution/estimate/next_steps"}
  ],
  "risk_notes": ["リスク・見落としに注意点1", "リスク・注意点2"]
}
"""


class AnalysisError(Exception):
    """Ollamaでの解析に失敗した際に投げる例外。メッセージはそのままユーザーに表示する想定。"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise AnalysisError("AIの応答からJSONを抽出できませんでした。")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise AnalysisError(f"AIの応答の解析に失敗しました: {exc}") from exc


def analyze_text(raw_text: str) -> dict:
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": raw_text},
                ],
                "stream": False,
                "format": "json",
            },
            timeout=300,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise AnalysisError(
            "Ollamaに接続できませんでした。Ollamaが起動しているか確認してください(ollama serve)。"
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise AnalysisError("Ollamaの応答がタイムアウトしました。") from exc
    except requests.exceptions.RequestException as exc:
        raise AnalysisError(f"Ollamaへのリクエストに失敗しました: {exc}") from exc

    data = response.json()
    content = data.get("message", {}).get("content", "")
    return _extract_json(content)
