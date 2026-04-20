from typing import TypedDict, Optional
import sys
from pathlib import Path
from langgraph.graph import StateGraph, END

if __package__ is None or __package__ == "":
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from data_ingestion.ingest import FDAClinicalData, fetch_fda_label
from services.ai_chat import generate_clinical_report

class ClinicalState(TypedDict):
    drug_name: str
    raw_fda_data: Optional[FDAClinicalData]
    clinical_analysis: Optional[str]
    needs_more_info: bool

def fetch_data_node(state: ClinicalState):
    print(f"🔍 Buscando datos en OpenFDA para: {state['drug_name']}")
    data = fetch_fda_label(state['drug_name']) 
    return {"raw_fda_data": data}

def analyze_protocol_node(state: ClinicalState):
    print("🧠 Analizando mecanismos de acción y eventos adversos...")
    reporte = generate_clinical_report(state['raw_fda_data'])
    return {"clinical_analysis": reporte}

def quality_control_node(state: ClinicalState):
    print("⚖️ Verificando integridad de los datos clínicos...")
    reporte_actual = state['clinical_analysis']
    
    # Patrones que indican falta de datos
    flags_faltantes = ["No disponible", "N/A", "no se encontró"]
    
    # Si encontramos algún flag, agregamos la alerta
    if any(flag in reporte_actual for flag in flags_faltantes):
        print("⚠️ ALERTA: Datos incompletos detectados. Inyectando disclaimer de seguridad.")
        
        alerta_gcto = (
            "\n\n=======================================================\n"
            "⚠️ ALERTA DE INTEGRIDAD DE DATOS (QA/QC):\n"
            "Este reporte preliminar contiene secciones con información 'No disponible' "
            "en los registros de OpenFDA. Por protocolo de GCTO, se requiere la "
            "revisión manual de un Medical Monitor o CRA antes de su inclusión "
            "en el diseño del ensayo clínico.\n"
            "======================================================="
        )
        
        # Actualizamos el reporte con la alerta
        return {"clinical_analysis": reporte_actual + alerta_gcto}
    
    # Si todo está perfecto, el reporte pasa limpio
    print("✅ Check de calidad superado.")
    return {"clinical_analysis": reporte_actual}
workflow = StateGraph(ClinicalState)

workflow.add_node("fetch", fetch_data_node)
workflow.add_node("analyze", analyze_protocol_node)
workflow.add_node("quality", quality_control_node)

workflow.set_entry_point("fetch")

workflow.add_edge("fetch", "analyze")
workflow.add_edge("analyze", "quality")


def decide_next_step(state: ClinicalState):
    if state["needs_more_info"]:
        return "re_fetch_or_alert" 
    return "finish"

workflow.add_conditional_edges(
    "quality",
    decide_next_step,
    {
        "re_fetch_or_alert": "fetch", # En un sistema real buscaría en otra fuente
        "finish": END
    }
)

app = workflow.compile()

if __name__ == "__main__":
    initial_state: ClinicalState = {
        "drug_name": "Finasteride",
        "raw_fda_data": None,
        "clinical_analysis": None,
        "needs_more_info": False,
    }
    
    final_state = app.invoke(initial_state)
    print("✅ Protocolo clínico generado:")
    print(final_state["clinical_analysis"])