from pathlib import Path
import sys
import json

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.graph_flow import run_clinical_flow


app = FastAPI(title="FDA-GraphAI Demo", version="1.0.0")

templates = Jinja2Templates(directory=str(project_root / "web" / "templates"))
app.mount("/static", StaticFiles(directory=str(project_root / "web" / "static")), name="static")
app.mount("/audit-reports", StaticFiles(directory=str(project_root / "audit_reports")), name="audit_reports")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "result": None,
            "error": None,
        },
    )


@app.post("/analyze", response_class=HTMLResponse)
def analyze(request: Request, drug_name: str = Form(...)):
    cleaned_name = drug_name.strip()
    if not cleaned_name:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "result": None,
                "error": "Please enter a valid drug name.",
            },
            status_code=400,
        )

    try:
        final_state, audit_path = run_clinical_flow(cleaned_name)
        audit_file_name = Path(audit_path).name
        result = {
            "drug_name": cleaned_name,
            "clinical_analysis": final_state.get("clinical_analysis") or "No report generated.",
            "parsed_adverse_events": json.dumps(final_state.get("parsed_adverse_events") or {}, indent=2, ensure_ascii=False),
            "needs_more_info": final_state.get("needs_more_info", False),
            "fallback": final_state.get("ct_fallback_data"),
            "audit_path": str(Path(audit_path).resolve()),
            "audit_download_url": f"/audit-reports/{audit_file_name}",
        }
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "result": result,
                "error": None,
            },
        )
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "result": None,
                "error": f"Pipeline execution failed: {exc}",
            },
            status_code=500,
        )


@app.get("/health")
def health():
    return {"status": "ok"}
