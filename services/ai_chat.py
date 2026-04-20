from langchain_google_genai import ChatGoogleGenerativeAI
import dotenv 
import os 
import sys
from pathlib import Path

# Permite ejecutar este archivo directamente sin romper imports por estructura de directorios.
if __package__ is None or __package__ == "":
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from data_ingestion.ingest import fetch_fda_label, FDAClinicalData

dotenv.load_dotenv()  # Carga las variables de entorno desde el archivo .env
google_api_key = dotenv.get_key(dotenv.find_dotenv(), "GOOGLE_API_KEY")

model = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        temperature=1.0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        google_api_key=google_api_key,
    )

def generate_clinical_report(fda_data: FDAClinicalData):
    """Transforma datos crudos en un reporte de nivel investigación clínica."""
    
    prompt = f"""
    ACTUAR COMO: Especialista en Farmacovigilancia de GCTO Argentina.
    CONTEXTO: Estamos evaluando la viabilidad de un nuevo protocolo clínico.
    DATOS TÉCNICOS (FDA):
    - Molécula: {fda_data.generic_name}
    - Mecanismo: {fda_data.mechanism_of_action}
    - Eventos Adversos: {fda_data.adverse_reactions}
    
    TAREA: Generar un reporte técnico de 3 párrafos resaltando:
    1. Resumen del Mecanismo de Acción.
    2. Riesgos críticos detectados que podrían afectar la seguridad de los sujetos.
    3. Sugerencia de monitoreo para el ensayo clínico basado en la toxicidad reportada.
    
    FORMATO: Profesional, científico y directo.
    """

    messages = [
        ("system", prompt),
        ("human", "Por favor, genera el reporte clínico basado en los datos proporcionados.")
    ]
    
    response = model.invoke(messages)
    return response.text

if __name__ == "__main__":
    # Esto es lo que mostrarías en una demo para Merck
    reporte_final = generate_clinical_report(fetch_fda_label("Atorvastatin"))
    print(reporte_final)