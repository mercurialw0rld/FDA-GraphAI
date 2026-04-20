from pydantic import BaseModel, Field
from typing import List, Optional
import requests

class FDAClinicalData(BaseModel):
    """Esquema para asegurar la integridad de los datos de investigación."""
    brand_name: str = Field(..., description="Nombre comercial del fármaco")
    generic_name: str = Field(..., description="Nombre genérico/molécula")
    mechanism_of_action: Optional[str] = Field(None, description="Mecanismo de acción biológico")
    adverse_reactions: Optional[str] = Field(None, description="Reporte de reacciones adversas")
    indications: Optional[str] = Field(None, description="Uso clínico y protocolos")

def fetch_fda_label(drug_name: str):
    base_url = "https://api.fda.gov/drug/label.json"
    params = {
        "search": f'openfda.brand_name:"{drug_name}"',
        "limit": 1
    }  
    response = requests.get(base_url, params=params, timeout=15)
    
    
    if response.status_code != 200:
        print(f"Error: No se encontró información para {drug_name}")
        return None
    
    results = response.json().get('results', [])
    if not results:
        print(f"Error: No se encontró información para {drug_name}")
        return None

    data = results[0]
    openfda = data.get('openfda', {})

    def first_or_default(value, default):
        if isinstance(value, list) and value:
            return value[0]
        if isinstance(value, str) and value:
            return value
        return default
    
    clinical_info = FDAClinicalData(
        brand_name=first_or_default(openfda.get('brand_name'), drug_name),
        generic_name=first_or_default(openfda.get('generic_name'), "N/A"),
        mechanism_of_action=first_or_default(data.get('mechanism_of_action'), "No disponible"),
        adverse_reactions=first_or_default(data.get('adverse_reactions'), "No disponible"),
        indications=first_or_default(data.get('indications_and_usage'), "No disponible")
    )
    
    return clinical_info

def fetch_clinicaltrials_fallback(drug_name: str) -> dict:
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {"query.term": drug_name, "pageSize": 3, "fields": "protocolSection"}
    response = requests.get(url, params=params, timeout=15)
    studies = response.json().get("studies", [])

    return {"studies_found": len(studies), "raw": studies}

class AdverseEvent(BaseModel):
    event: str
    severity: str  # "Critical" | "Major" | "Minor"
    frequency: Optional[str]  # "common", "rare", etc.
    system_organ_class: Optional[str]  # cardiovascular, hepatic, etc.

class StructuredAdverseEvents(BaseModel):
    events: List[AdverseEvent]
    total_critical: int
    red_flags: List[str] 


if __name__ == "__main__":
    # Prueba rápida
    drug = "Atorvastatin"
    fda_data = fetch_clinicaltrials_fallback(drug)
    print(f"Datos de ClinicalTrials para {drug}: {fda_data['studies_found']} estudios encontrados.")


