from reportcomores.report_templates import rptBeneficiaryAmg
from reportcomores.models import generate_carte_amg_query

report_definitions = [
    {
        "name": "carte_amg",
        "engine": 0,
        "default_report": rptBeneficiaryAmg.template,
        "description": "Carte AMG",
        "module": "reportcomores",
        "python_query": generate_carte_amg_query,
        "permission": ["131217"],
    }
]
