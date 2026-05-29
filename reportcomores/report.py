from reportcomores.report_templates import reportAMG_recto, reportAMG_verso, rptInvoiceFosaPrivate,\
    rptInvoiceFosaPublic, rptMembership
from reportcomores.models import generate_carte_amg_query, invoice_private_fosa_query,\
    invoice_public_fosa_query, report_membership_query

report_definitions = [
    {
        "name": "carte_amg",
        "engine": 0,
        "default_report": reportAMG_recto.template,
        "description": "Carte AMG",
        "module": "reportcomores",
        "python_query": generate_carte_amg_query,
        "permission": ["131215"],
    },
    {
        "name": "carte_amg_verso",
        "engine": 0,
        "default_report": reportAMG_verso.template,
        "description": "Carte AMG",
        "module": "reportcomores",
        "python_query": generate_carte_amg_query,
        "permission": ["131215"],
    },
    {
        "name": "invoice_private_fosa",
        "engine": 0,
        "default_report": rptInvoiceFosaPrivate.template,
        "description": "Facture globale par FOSA Privée",
        "module": "reportcomores",
        "python_query": invoice_private_fosa_query,
        "permission": ["131215"],
    },
    {
        "name": "invoice_public_fosa",
        "engine": 0,
        "default_report": rptInvoiceFosaPublic.template,
        "description": "Facture globale par FOSA Publique",
        "module": "reportcomores",
        "python_query": invoice_public_fosa_query,
        "permission": ["131215"],
    },
    {
        "name": "membership_report",
        "engine": 0,
        "default_report": rptMembership.template,
        "description": "Rapport d'adhésion pour familles polygames",
        "module": "reportcomores",
        "python_query": report_membership_query,
        "permission": ["131215"],
    }
]
