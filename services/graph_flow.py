from typing import TypedDict, Optional
import sys
from pathlib import Path
import json
from langgraph.graph import StateGraph, END

if __package__ is None or __package__ == "":
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from data_ingestion.ingest import FDAClinicalData, fetch_fda_label, fetch_clinicaltrials_fallback
from services.ai_chat import model, generate_clinical_report
from services.audit import clear_audit_log, create_audit_node, export_audit_report

class ClinicalState(TypedDict):
    drug_name: str
    raw_fda_data: Optional[FDAClinicalData]
    adverse_effect_template: dict
    clinical_analysis: Optional[str]
    needs_more_info: bool
    ct_fallback_data: Optional[dict]
    parsed_adverse_events: Optional[dict]


DEFAULT_ADVERSE_EFFECT_TEMPLATE = {
    "events": [
        {
            "event": "",
            "severity": "Minor",
            "frequency": None,
            "system_organ_class": None,
        }
    ],
    "total_critical": 0,
    "red_flags": [],
}


def fetch_data_node(state: ClinicalState):
    print(f"Fetching OpenFDA data for: {state['drug_name']}")
    data = fetch_fda_label(state['drug_name']) 

    # Canonical template used to normalize adverse-event parsing.
    adverse_template = DEFAULT_ADVERSE_EFFECT_TEMPLATE.copy()

    return {
        "raw_fda_data": data,
        "adverse_effect_template": adverse_template,
    }

def analyze_protocol_node(state: ClinicalState):
    print("Analyzing mechanism of action and adverse events...")
    reporte = generate_clinical_report(state['raw_fda_data'])
    return {"clinical_analysis": reporte}

def quality_control_node(state: ClinicalState):
    print("Running clinical data quality checks...")
    reporte_actual = state['clinical_analysis'] or ""
    
    # Patterns indicating missing or low-quality data in the generated report.
    missing_data_flags = ["No disponible", "N/A", "no se encontró", "Not available", "not found"]

    
    if any(flag in reporte_actual for flag in missing_data_flags):
        return {"clinical_analysis": reporte_actual, "needs_more_info": True}
    
    print("Quality check passed.")
    return {"clinical_analysis": reporte_actual, "needs_more_info": False}

def fallback_clinicaltrials_node(state: ClinicalState):
    print("Incomplete FDA data detected -> querying ClinicalTrials.gov...")
    ct_data = fetch_clinicaltrials_fallback(state["drug_name"])
    # Could merge with raw_fda_data or enrich downstream state in future iterations.
    return {"ct_fallback_data": ct_data, "needs_more_info": False}

def parse_adverse_events_node(state: ClinicalState):
    """Converts raw adverse-event text into a structured, auditable dictionary."""
    raw_fda = state.get("raw_fda_data")
    raw_ae = raw_fda.adverse_reactions if raw_fda else "No disponible"
    adverse_template = state.get("adverse_effect_template") or DEFAULT_ADVERSE_EFFECT_TEMPLATE.copy()

    # If there is no usable adverse-event signal, return a valid default payload.
    if not raw_ae or raw_ae == "No disponible":
        return {"parsed_adverse_events": adverse_template}

    messages = [
        ("system", "You are an expert parser extracting adverse events from FDA technical text."),
        (
            "human",
            (
                f"Extract adverse events from the following text and classify them as JSON.\n\n{raw_ae}\n\n"
                "Use EXACTLY this template (same structure and keys) and fill in values: "
                f"{json.dumps(adverse_template, ensure_ascii=True)}\n"
                "Rules: severity can only be Critical, Major, or Minor; total_critical must be an integer; red_flags must be a list of strings, unknown prevalence should be listed as 'No information available'."
            ),
        ),
    ]

    response = model.invoke(messages)
    raw_response = response.text if hasattr(response, "text") else str(response)

    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        structured = json.loads(cleaned.strip())

        if not isinstance(structured, dict):
            raise ValueError("Parsed response is not a JSON dictionary")

        print("Adverse events parsed successfully.")
        return {"parsed_adverse_events": structured}
    except Exception as e:        
        print("Error while parsing adverse events:", e)
        return {"parsed_adverse_events": adverse_template}
    
def decide_next_step(state: ClinicalState):
    if state["needs_more_info"]:
        return "re_fetch_or_alert" 
    return "finish"

workflow = StateGraph(ClinicalState)

workflow.add_node("fetch", create_audit_node("fetch", fetch_data_node))
workflow.add_node("parse_ae", create_audit_node("parse_ae", parse_adverse_events_node))
workflow.add_node("analyze", create_audit_node("analyze", analyze_protocol_node))
workflow.add_node("quality", create_audit_node("quality", quality_control_node))
workflow.add_node("re_fetch_or_alert", create_audit_node("re_fetch_or_alert", fallback_clinicaltrials_node))

workflow.set_entry_point("fetch")

workflow.add_edge("fetch", "parse_ae")
workflow.add_edge("parse_ae", "analyze")
workflow.add_edge("analyze", "quality")

workflow.add_conditional_edges(
    "quality",
    decide_next_step,
    {
        "re_fetch_or_alert": "re_fetch_or_alert",
        "finish": END
    }
)

app = workflow.compile()


def run_clinical_flow(drug_name: str) -> tuple[dict, str]:
    """Runs the graph for a drug and exports an audit report for that execution."""
    clear_audit_log()
    initial_state: ClinicalState = {
        "drug_name": drug_name,
        "raw_fda_data": None,
        "adverse_effect_template": DEFAULT_ADVERSE_EFFECT_TEMPLATE.copy(),
        "clinical_analysis": None,
        "needs_more_info": False,
        "ct_fallback_data": None,
        "parsed_adverse_events": None,
    }

    final_state = app.invoke(initial_state)
    report_path = export_audit_report(initial_state["drug_name"])
    return final_state, str(report_path)

if __name__ == "__main__":
    final_state, report_path = run_clinical_flow("Sertraline")
    print("Clinical protocol generated:")
    print(final_state["clinical_analysis"])
    print("Structured adverse events:")
    print(json.dumps(final_state["parsed_adverse_events"], indent=2))
    print(f"Audit report exported to: {report_path}")