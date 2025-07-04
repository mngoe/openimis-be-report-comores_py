from reportcomores.report_templates import rptBeneficiaryAmg, rptInvoiceFosaPrivate,\
    rptInvoiceFosaPublic, rptMembership, rptInvoiceAfd
from reportcomores.models import generate_carte_amg_query, invoice_private_fosa_query,\
    invoice_public_fosa_query, report_membership_query, invoice_afd_query

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
    },
    {
        "name": "invoice_afd_report",
        "engine": 0,
        "default_report": rptInvoiceAfd.template,
        "description": "Facture globale AFD",
        "module": "reportcomores",
        "python_query": invoice_afd_query,
        "permission": ["131215"],
    }
]
