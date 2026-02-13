from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, Request

pytest.importorskip("itsdangerous")
pytest.importorskip("httpx")
from starlette.middleware.sessions import SessionMiddleware

from website.backend.dependencies import get_db
from website.backend.routers import greatshot as greatshot_router
from website.backend.services.greatshot_store import GreatshotStorageService

from fastapi.testclient import TestClient


class _FakeJobService:
    def __init__(self):
        self.analysis_jobs: list[str] = []
        self.render_jobs: list[str] = []

    async def enqueue_analysis(self, demo_id: str):
        self.analysis_jobs.append(demo_id)

    async def enqueue_render(self, render_id: str):
        self.render_jobs.append(render_id)


class _FakeDB:
    def __init__(self):
        self.greatshot_demos: dict[str, dict[str, Any]] = {}
        self.greatshot_analysis: dict[str, dict[str, Any]] = {}

    async def execute(self, query: str, params=None, *extra):
        query = " ".join(query.split())
        params = params or ()

        if "INSERT INTO greatshot_demos" in query:
            (
                demo_id,
                user_id,
                original_filename,
                stored_path,
                extension,
                file_size_bytes,
                content_hash_sha256,
            ) = params
            self.greatshot_demos[demo_id] = {
                "id": demo_id,
                "user_id": int(user_id),
                "original_filename": original_filename,
                "stored_path": stored_path,
                "extension": extension,
                "file_size_bytes": file_size_bytes,
                "content_hash_sha256": content_hash_sha256,
                "status": "uploaded",
                "error": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "metadata_json": None,
                "warnings_json": None,
                "analysis_json_path": None,
                "report_txt_path": None,
                "processing_started_at": None,
                "processing_finished_at": None,
            }
            return

        if "UPDATE greatshot_demos" in query and "analysis_json_path" in query:
            demo_id, metadata_json, warnings_json, analysis_json_path, report_txt_path = params
            row = self.greatshot_demos[demo_id]
            row["status"] = "analyzed"
            row["metadata_json"] = metadata_json
            row["warnings_json"] = warnings_json
            row["analysis_json_path"] = analysis_json_path
            row["report_txt_path"] = report_txt_path
            row["processing_finished_at"] = datetime.utcnow()
            return

        if "INSERT INTO greatshot_analysis" in query:
            demo_id, metadata_json, stats_json, events_json = params
            self.greatshot_analysis[demo_id] = {
                "metadata_json": metadata_json,
                "stats_json": stats_json,
                "events_json": events_json,
                "created_at": datetime.utcnow(),
            }
            return

        if "DELETE FROM greatshot_highlights" in query:
            return

    async def fetch_all(self, query: str, params=None):
        query = " ".join(query.split())
        params = params or ()

        if "FROM greatshot_demos" in query and "WHERE user_id = $1" in query:
            user_id = int(params[0])
            rows = []
            for row in self.greatshot_demos.values():
                if row["user_id"] != user_id:
                    continue
                rows.append(
                    (
                        row["id"],
                        row["original_filename"],
                        row["status"],
                        row["error"],
                        row["created_at"],
                        row["metadata_json"],
                        row["warnings_json"],
                        row["processing_started_at"],
                        row["processing_finished_at"],
                        0,  # highlight_count
                        0,  # render_job_count
                        0,  # rendered_count
                    )
                )
            rows.sort(key=lambda item: item[4], reverse=True)
            return rows

        if "FROM greatshot_highlights" in query:
            return []

        if "FROM greatshot_renders" in query:
            return []

        return []

    async def fetch_one(self, query: str, params=None):
        query = " ".join(query.split())
        params = params or ()

        if "SELECT id, original_filename, status, error, created_at, metadata_json, warnings_json, analysis_json_path, report_txt_path" in query:
            demo_id, user_id = params
            row = self.greatshot_demos.get(demo_id)
            if not row or row["user_id"] != int(user_id):
                return None
            return (
                row["id"],
                row["original_filename"],
                row["status"],
                row["error"],
                row["created_at"],
                row["metadata_json"],
                row["warnings_json"],
                row["analysis_json_path"],
                row["report_txt_path"],
                row["processing_started_at"],
                row["processing_finished_at"],
            )

        if query.startswith("SELECT metadata_json FROM greatshot_demos WHERE id = $1 AND user_id = $2"):
            demo_id, user_id = params
            row = self.greatshot_demos.get(demo_id)
            if not row or row["user_id"] != int(user_id):
                return None
            return (row["metadata_json"],)

        if "SELECT metadata_json, stats_json, events_json, created_at" in query:
            demo_id = params[0]
            row = self.greatshot_analysis.get(demo_id)
            if not row:
                return None
            return (
                row["metadata_json"],
                row["stats_json"],
                row["events_json"],
                row["created_at"],
            )

        if query.startswith("SELECT analysis_json_path FROM greatshot_demos"):
            demo_id = params[0]
            row = self.greatshot_demos.get(demo_id)
            if not row:
                return None
            if len(params) > 1 and row["user_id"] != int(params[1]):
                return None
            return (row["analysis_json_path"],)

        if query.startswith("SELECT report_txt_path FROM greatshot_demos"):
            demo_id, user_id = params
            row = self.greatshot_demos.get(demo_id)
            if not row or row["user_id"] != int(user_id):
                return None
            return (row["report_txt_path"],)

        if query.startswith("SELECT id FROM greatshot_demos WHERE id = $1 AND user_id = $2"):
            demo_id, user_id = params
            row = self.greatshot_demos.get(demo_id)
            if row and row["user_id"] == int(user_id):
                return (row["id"],)
            return None

        return None


def _valid_demo_bytes() -> bytes:
    header = (1).to_bytes(4, "little", signed=True) + (64).to_bytes(4, "little", signed=True)
    return header + (b"\x00" * 128)


def test_upload_list_detail_and_reports_with_mocked_job(tmp_path: Path, monkeypatch):
    fake_db = _FakeDB()
    fake_jobs = _FakeJobService()

    storage = GreatshotStorageService(project_root=tmp_path)
    monkeypatch.setattr(greatshot_router, "storage", storage)
    monkeypatch.setattr(greatshot_router, "get_greatshot_job_service", lambda: fake_jobs)

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-session-secret")

    @app.get("/test/login")
    async def _login(request: Request):
        request.session["user"] = {"id": "999", "username": "tester"}
        return {"ok": True}

    async def _db_override():
        yield fake_db

    app.dependency_overrides[get_db] = _db_override
    app.include_router(greatshot_router.router, prefix="/api")

    client = TestClient(app)
    login_resp = client.get("/test/login")
    assert login_resp.status_code == 200

    upload_resp = client.post(
        "/api/greatshot/upload",
        files={"file": ("sample.dm_84", _valid_demo_bytes(), "application/octet-stream")},
    )
    assert upload_resp.status_code == 200

    payload = upload_resp.json()
    demo_id = payload["demo_id"]
    assert demo_id in fake_db.greatshot_demos
    assert demo_id in fake_jobs.analysis_jobs

    artifacts_dir = storage.artifacts_dir(demo_id)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    analysis_path = artifacts_dir / "analysis.json"
    report_path = artifacts_dir / "report.txt"

    analysis_doc = {
        "metadata": {"map": "etl_goldrush", "duration_ms": 30000, "mod": "Legacy", "mod_version": "v2.83.1"},
        "stats": {"player_count": 2, "kill_count": 3, "chat_count": 1},
        "timeline": [{"t_ms": 1000, "type": "chat", "attacker": "PlayerOne", "message": "go"}],
    }
    analysis_path.write_text(json.dumps(analysis_doc), encoding="utf-8")
    report_path.write_text("report body\n", encoding="utf-8")

    fake_db.greatshot_demos[demo_id]["status"] = "analyzed"
    fake_db.greatshot_demos[demo_id]["metadata_json"] = json.dumps(analysis_doc["metadata"])
    fake_db.greatshot_demos[demo_id]["analysis_json_path"] = str(analysis_path)
    fake_db.greatshot_demos[demo_id]["report_txt_path"] = str(report_path)
    fake_db.greatshot_analysis[demo_id] = {
        "metadata_json": json.dumps(analysis_doc["metadata"]),
        "stats_json": json.dumps(analysis_doc["stats"]),
        "events_json": json.dumps(analysis_doc["timeline"]),
        "created_at": datetime.utcnow(),
    }

    list_resp = client.get("/api/greatshot")
    assert list_resp.status_code == 200
    assert list_resp.json()["items"][0]["id"] == demo_id

    detail_resp = client.get(f"/api/greatshot/{demo_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"] == "analyzed"
    assert detail["downloads"]["json"]
    assert detail["downloads"]["txt"]

    json_report_resp = client.get(f"/api/greatshot/{demo_id}/report.json")
    assert json_report_resp.status_code == 200
    assert json_report_resp.json()["metadata"]["map"] == "etl_goldrush"

    txt_report_resp = client.get(f"/api/greatshot/{demo_id}/report.txt")
    assert txt_report_resp.status_code == 200
    assert "report body" in txt_report_resp.text


def test_crossref_endpoint_returns_200_for_no_match_and_match(tmp_path: Path, monkeypatch):
    fake_db = _FakeDB()
    fake_jobs = _FakeJobService()

    storage = GreatshotStorageService(project_root=tmp_path)
    monkeypatch.setattr(greatshot_router, "storage", storage)
    monkeypatch.setattr(greatshot_router, "get_greatshot_job_service", lambda: fake_jobs)

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-session-secret")

    @app.get("/test/login")
    async def _login(request: Request):
        request.session["user"] = {"id": "999", "username": "tester"}
        return {"ok": True}

    async def _db_override():
        yield fake_db

    app.dependency_overrides[get_db] = _db_override
    app.include_router(greatshot_router.router, prefix="/api")

    client = TestClient(app)
    assert client.get("/test/login").status_code == 200

    upload_resp = client.post(
        "/api/greatshot/upload",
        files={"file": ("crossref.dm_84", _valid_demo_bytes(), "application/octet-stream")},
    )
    assert upload_resp.status_code == 200
    demo_id = upload_resp.json()["demo_id"]

    # Route only attempts crossref when metadata exists.
    fake_db.greatshot_demos[demo_id]["metadata_json"] = json.dumps(
        {"map": "supply", "filename": "2026-02-12-crossref.dm_84", "rounds": []}
    )

    async def _no_match(*_args, **_kwargs):
        return None

    monkeypatch.setattr(greatshot_router, "find_matching_round", _no_match)
    resp_no_match = client.get(f"/api/greatshot/{demo_id}/crossref")
    assert resp_no_match.status_code == 200
    assert resp_no_match.json()["matched"] is False

    async def _match(*_args, **_kwargs):
        return {
            "round_id": 9841,
            "match_id": "2026-02-12-115656",
            "round_number": 2,
            "map_name": "supply",
            "confidence": 90.0,
            "match_details": ["map", "duration", "winner"],
        }

    async def _enrich(*_args, **_kwargs):
        return {
            "PlayerOne": {"kills": 20, "deaths": 10},
            "PlayerTwo": {"kills": 15, "deaths": 11},
        }

    async def _comparison(*_args, **_kwargs):
        return [{"demo_name": "PlayerOne", "db_name": "PlayerOne", "matched": True}]

    monkeypatch.setattr(greatshot_router, "find_matching_round", _match)
    monkeypatch.setattr(greatshot_router, "enrich_with_db_stats", _enrich)
    monkeypatch.setattr(greatshot_router, "build_comparison", _comparison)

    resp_match = client.get(f"/api/greatshot/{demo_id}/crossref")
    assert resp_match.status_code == 200
    payload = resp_match.json()
    assert payload["matched"] is True
    assert payload["round"]["round_id"] == 9841
    assert "db_player_stats" in payload
    assert "comparison" in payload
