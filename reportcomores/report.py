from reportcomores.report_templates import rptBeneficiaryAmg, rptInvoiceFosaPrivate,\
    rptInvoiceFosaPublic, rptMembership,rptPrescripteur
from reportcomores.models import generate_carte_amg_query, invoice_private_fosa_query,\
    invoice_public_fosa_query, report_membership_query,report_prescriber_query

report_definitions = [
    {
        "name": "carte_amg",
        "engine": 0,
        "default_report": rptBeneficiaryAmg.template,
        "description": "Carte AMG",
        "module": "reportcomores",
        "python_query": generate_carte_amg_query,
        "permission": ["131214"],
    },
    {
        "name": "invoice_private_fosa",
        "engine": 0,
        "default_report": rptInvoiceFosaPrivate.template,
        "description": "Facture globale par FOSA Privée",
        "module": "reportcomores",
        "python_query": invoice_private_fosa_query,
        "permission": ["131214"],
    },
    {
        "name": "invoice_public_fosa",
        "engine": 0,
        "default_report": rptInvoiceFosaPublic.template,
        "description": "Facture globale par FOSA Publique",
        "module": "reportcomores",
        "python_query": invoice_public_fosa_query,
        "permission": ["131214"],
    },
    {
        "name": "membership_report",
        "engine": 0,
        "default_report": rptMembership.template,
        "description": "Rapport d'adhésion pour familles polygames",
        "module": "reportcomores",
        "python_query": report_membership_query,
        "permission": ["131214"],
    },
    {
        "name": "prescripteur_reporting",
        "engine": 0,
        "default_report": rptPrescripteur.template,
        "description": "Rapport Prescripteur",
        "module": "reportcomores",
        "python_query": report_prescriber_query,
        "permission": ["131214"],
    }  
]
