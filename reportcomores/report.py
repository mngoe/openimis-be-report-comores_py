from reportcomores.report_templates import rptBeneficiaryAmg, rptInvoiceFosag
from reportcomores.models import generate_carte_amg_query, invoice_private_fosa_query,\
    invoice_public_fosa_query

report_definitions = [
    {
        "name": "carte_amg",
        "engine": 0,
        "default_report": rptBeneficiaryAmg.template,
        "description": "Carte AMG",
        "module": "reportcomores",
        "python_query": generate_carte_amg_query,
        "permission": ["131215"],
    },
    {
        "name": "invoice_private_fosa",
        "engine": 0,
        "default_report": rptInvoiceFosag.template,
        "description": "Facture globale par FOSA Privée",
        "module": "reportcomores",
        "python_query": invoice_private_fosa_query,
        "permission": ["131215"],
    },
    {
        "name": "invoice_public_fosa",
        "engine": 0,
        "default_report": rptInvoiceFosag.template,
        "description": "Facture globale par FOSA Publique",
        "module": "reportcomores",
        "python_query": invoice_public_fosa_query,
        "permission": ["131215"],
    }
]
