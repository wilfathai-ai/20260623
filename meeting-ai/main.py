"""商談議事録AI - FastAPI サーバー"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database
from analyzer import AnalysisError, analyze_text
from file_parser import FileParseError, parse_file

app = FastAPI(title="商談議事録AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

database.init_db()


class SaveRequest(BaseModel):
    raw_text: str
    analysis: dict


@app.on_event("startup")
async def startup() -> None:
    database.init_db()


@app.post("/api/analyze")
async def api_analyze(file: UploadFile | None = File(None), text: str | None = Form(None)):
    raw_text: str

    if file is not None:
        suffix = os.path.splitext(file.filename or "")[1]
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = tmp.name
            async with aiofiles.open(tmp_path, "wb") as out:
                await out.write(await file.read())
            raw_text = parse_file(tmp_path, file.filename or "")
        except FileParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
    elif text and text.strip():
        raw_text = text.strip()
    else:
        raise HTTPException(status_code=400, detail="ファイルまたはテキストを指定してください。")

    try:
        analysis = analyze_text(raw_text)
    except AnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    analysis.setdefault("client_name", "不明")
    analysis.setdefault("meeting_date", date.today().isoformat())

    return JSONResponse({"raw_text": raw_text, "analysis": analysis})


@app.post("/api/save")
async def api_save(payload: SaveRequest):
    analysis = payload.analysis
    meeting_id = database.save_meeting(
        client_name=analysis.get("client_name", "不明"),
        meeting_date=analysis.get("meeting_date", date.today().isoformat()),
        raw_text=payload.raw_text,
        analysis_json=json.dumps(analysis, ensure_ascii=False),
    )
    return {"id": meeting_id}


@app.get("/api/meetings")
async def api_list_meetings():
    rows = database.list_meetings()
    result = []
    for row in rows:
        analysis = json.loads(row["analysis_json"]) if row["analysis_json"] else {}
        result.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "client_name": row["client_name"],
                "meeting_date": row["meeting_date"],
                "summary": analysis.get("summary", ""),
            }
        )
    return result


@app.get("/api/meetings/{meeting_id}")
async def api_get_meeting(meeting_id: int):
    row = database.get_meeting(meeting_id)
    if not row:
        raise HTTPException(status_code=404, detail="議事録が見つかりません。")
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "client_name": row["client_name"],
        "meeting_date": row["meeting_date"],
        "raw_text": row["raw_text"],
        "analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else {},
    }


@app.delete("/api/meetings/{meeting_id}")
async def api_delete_meeting(meeting_id: int):
    ok = database.delete_meeting(meeting_id)
    if not ok:
        raise HTTPException(status_code=404, detail="議事録が見つかりません。")
    return {"deleted": True}


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")
