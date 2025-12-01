from django.db import models
from django.db.models import OuterRef, Subquery, Avg, Q
from report.services import run_stored_proc_report
from insuree.models import Insuree, Family
import qrcode
from io import BytesIO
import base64, core, datetime
from insuree.models import InsureePolicy
import calendar
from location.models import Location, HealthFacility
from claim.models import Claim, ClaimService, ClaimItem,Speciality,Status,Prescriber
import random
from policy.models import Policy
import imghdr, os
from PIL import Image
from contribution.models import Premium
from django.utils.translation import gettext as _
from django.utils.translation import override
from collections import Counter
import traceback
import datetime
import json
from claim.models import ClaimAdmin, Claim, ClaimService, ClaimItem, Prescriber
from medical.models import Service, Item
from location.models import HealthFacility
from policy.values import policy_values



val_de_zero = [
    'million', 'milliard', 'billion',
    'quadrillion', 'quintillion', 'sextillion',
    'septillion', 'octillion', 'nonillion',
    'décillion', 'undecillion', 'duodecillion',
    'tredecillion', 'quattuordecillion', 'sexdecillion',
    'septendecillion', 'octodecillion', 'icosillion', 'vigintillion'
]

to_19_fr = (
    'zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six',
    'sept', 'huit', 'neuf', 'dix', 'onze', 'douze', 'treize',
    'quatorze', 'quinze', 'seize', 'dix-sept', 'dix-huit', 'dix-neuf'
)

tens_fr  = (
    'vingt', 'trente', 'quarante', 'cinquante', 'soixante', 'soixante',
    'quatre-vingts', 'quatre-vingt'
)

denom_fr = (
    '', 'mille', 'million', 'milliard', 'billion', 'quadrillion',
    'quintillion', 'sextillion', 'septillion', 'octillion', 'nonillion',
    'décillion', 'undecillion', 'duodecillion', 'tredecillion',
    'quattuordecillion', 'sexdecillion', 'septendecillion',
    'octodecillion', 'icosillion', 'vigintillion'
)

denoms_fr = (
    '', 'mille', 'millions', 'milliards', 'billions', 'quadrillions',
    'quintillions', 'sextillions', 'septillions', 'octillions', 'nonillions',
    'décillions', 'undecillions', 'duodecillions', 'tredecillions',
    'quattuordecillions', 'sexdecillions', 'septendecillions',
    'octodecillions', 'icosillions', 'vigintillions'
)

def get_claim_status_display(status, rejection_reason=None):
    status_map = {
        1: "rejete",
        2: "entree", 
        4: "verifie",
        8: "traite",
        16: "valide"
    }
    stat = status_map.get(status, "inconnu")
    if status == 1 and rejection_reason is not None:
        rej = get_rejection_reason_display(rejection_reason)
        return f"{stat} - {rej}"
    return stat

def get_rejection_reason_display(reason):
    reason_map = {
        1: "item ou service invalide",
        2: "non dans liste de prix",
        3: "aucun produit trouve",
        4: "limitation categorie",
        5: "echec frequence",
# REJECTION_REASON_DUPLICATED = 6
        7: "famille",
# REJECTION_REASON_ICD_NOT_IN_LIST = 8
        9: "date cible",
        10: "type de soin",
        11: "max admissions hopital",
        12: "max visites",
        13: "max consultations",
        14: "max chirurgies",
        15: "max accouchements",
        16: "quantite depassee",
        17: "echec delai attente",
        19: "max prenatals",
        20: "reclamation invalide",
    }
    return reason_map.get(reason, "inconnu")


def get_service_category_display(code):
    """
    Returns the human-readable label for a medical service category.
    """
    service_map = {
        "S": "Surgery",
        "D": "Delivery",
        "A": "Antenatal",
        "H": "Hospitalization",
        "C": "Consultation",
        "O": "Other",
        "V": "Visit",
    }
    return service_map.get(code, "Inconnu")


def get_item_type_display(code):
    """
    Returns the human-readable label for a medical item type.
    """
    item_map = {
        "D": "Drug",
        "M": "Consumable",
    }
    return item_map.get(code, "Inconnu")

def get_act_type_display(code):
    """
    Returns the human-readable label for a medical item type.
    """
    item_map = {
        "1": "Service",
        "2": "Article",
    }
    return item_map.get(code, "Inconnu")


def _convert_nnn_fr(val):
    """
    \detail         convert a value < 1000 to french
        special cased because it is the level that kicks 
        off the < 100 special case.  The rest are
        more general.  This also allows you to
        get strings in the form of 'forty-five hundred' if called directly.
    \param  val     value(int or float) to convert
    \return         a string value
    """
    word = ''
    (mod, rem) = (val % 100, val // 100)
    if rem > 0:
        if (rem>1 and rem <10 and mod <= 0): 
             word = to_19_fr[rem] + ' cents'
        else: 
             word = to_19_fr[rem] + ' cent'
             
        if mod > 0:
            word += ' '
    if mod > 0:
        word += _convert_nn_fr(mod)
    return word

def _convert_nn_fr(val):
    """
    \brief       convert a value < 100 to French
    \param  val  value to convert 
    """
    if val < 20:
        return to_19_fr[val]
    for (dcap, dval) in ((k, 20 + (10 * v)) for (v, k) in enumerate(tens_fr)):
        if dval + 10 > val:
            if dval in (70,90):
                return dcap + '-' + to_19_fr[val % 10 + 10]
            if val % 10:
                return dcap + '-' + to_19_fr[val % 10]
            return dcap

def french_number(val):
    
    """
    \brief       Convert a numeric value to a french string
        Dispatch diffent kinds of number depending
        on their value (<100 or < 1000)
        Then create a for loop to rewrite cutted number.
    \param  val  value(int or float) to convert
    \return      a string value
    """
    
    if val < 100:
        return _convert_nn_fr(val)
    if val < 1000:
         return _convert_nnn_fr(val)
    for (didx, dval) in ((v - 1, 1000 ** v) for v in range(len(denom_fr))):
        if dval > val:
            mod = 1000 ** didx
            l = val // mod
            r = val - (l * mod)
            
            pref_final = _convert_nnn_fr(l)
            pref = pref_final.split(' ')
            if(pref[len(pref)-1] == ' cent'):
                pref[len(pref)-1] = " cents"
                pref_final = " ".join(x for x in pref)
            if l>1:    
                ret = pref_final + ' ' + denoms_fr[didx]
            else:
                ret = pref_final + ' ' + denom_fr[didx]
            if r > 0:
                ret = ret + ' ' + french_number(r)
            return ret

def amount_to_text_fr(number, currency):
    """
    \brief              convert amount value to french string
        reuse the french_number function
        to write the correct number
        in french, then add the specific cents for number < 0
        and add the currency to the string
    \param  number      the number to convert
    \param  currency    string value of the currency
    \return             the string amount in french
    """
    try:
        number = int(number)
    except:
        return 'Traduction error'
    number = '%.2f' % number
    units_name = currency
    list = str(number).split('.')
    start_word = french_number(abs(int(list[0])))

    #On enleve le un au debut de la somme écrite en lettre.
    liste = str(start_word).split(' ')
    for i in range(len(liste)):
        item = liste[i]
        tab=liste
        if item =='un':
            if i==0 and len(liste) > 1:
                if liste[i+1] not in val_de_zero:
                    tab[i]=""
            elif i > 0 and len(liste) > 1:
                if i < len(liste)-1:
                    if liste[i+1] not in val_de_zero:
                        if not liste[i-1] in ["cent", "cents"] and not (liste[i+1] in val_de_zero or liste[i+1] in denom_fr or liste[i+1] in denoms_fr):
                            tab[i]=""
            start_word = " ".join(x for x in tab)
    french_number(int(list[1]))
    final_result = start_word +' '+units_name
    return final_result

def generate_carte_amg_query(user, **kwargs):
    print("Carte AMG ", kwargs)
    ids = kwargs.get("insureeids", [])
    insurees_ids = []
    if ids:
        ids = ids.split(',')
        insurees_ids = [eval(i) for i in ids]
    
    insuree_list = Insuree.objects.filter(
        id__in=insurees_ids
    )
    
    insurees_data = []
    for insuree_obj in insuree_list:
        data = {}
        conjointe = ""
        chef_menage = ""
        chfid2 = ""
        chef_menage = (insuree_obj.last_name + " " + insuree_obj.other_names).rstrip()
        chfid = insuree_obj.chf_id
        if insuree_obj.family:
            family = insuree_obj.family
            if family.parent:
                # Cas famille polygamique
                try:
                    chef_principal = family.parent.head_insuree

                    # Vérifier s'il est assuré dans ce sous-ménage
                    is_chef_in_subfamily = Insuree.objects.filter(
                        family=family,
                        id=chef_principal.id,
                        validity_to__isnull=True
                    ).exists()

                    if is_chef_in_subfamily:
                        # Cas 3 : Le mari est aussi assuré du sous-ménage
                        data["FullFathersName"] = (chef_principal.last_name + " " + chef_principal.other_names)
                        data["chfid"] = chef_principal.chf_id
                        data["FullMothersName"] = chef_menage
                        data["chfid2"] = chfid
                    else:
                        # Cas 2 : Le mari n’est pas assuré ici, la femme est chef
                        data["FullFathersName"] = (insuree_obj.last_name + " " + insuree_obj.other_names)
                        data["chfid"] = insuree_obj.chf_id
                        data["FullMothersName"] = ""
                        data["chfid2"] = ""

                except Insuree.DoesNotExist:
                    # Chef principal introuvable, fallback sur assuré
                    data["FullFathersName"] = chef_menage
                    data["chfid"] = chfid
                    data["FullMothersName"] = ""
                    data["chfid2"] = ""
            else:
                # Cas famille simple
                members = Insuree.objects.filter(
                    family=family,
                    validity_to__isnull=True
                ).exclude(id=insuree_obj.id)

                # Chercher conjoint(e)
                for membre in members:
                    if membre.relationship and str(membre.relationship.relation).lower() in ["spouse", "époux"]:
                        conjointe = ( membre.last_name + " " + membre.other_names).rstrip()
                        chfid2 = membre.chf_id 
                        break

                data["FullFathersName"] = chef_menage
                data["chfid"] = chfid
                data["FullMothersName"] = conjointe
                data["chfid2"] = chfid2
        else:
            # Pas de famille associée : fallback
            data["FullFathersName"] = chef_menage
            data["chfid"] = chfid
            data["FullMothersName"] = ""
            data["chfid2"] = ""
                       
        insure_policies = InsureePolicy.objects.filter(
            insuree=insuree_obj.id, policy__status=2).order_by('-id')
        data["DateExpiration"] = ""
        data["dateEmission"] = datetime.datetime.now().strftime("%d/%m/%Y")
        if insure_policies:
            my_dict = {
                "01": "Janvier",
                "02": "Février",
                "03": "Mars",
                "04": "Avril",
                "05": "Mai",
                "06": "Juin",
                "07": "Juillet",
                "08": "Août",
                "09": "Septembre",
                "10": "Octobre",
                "11": "Novembre",
                "12": "Décembre"
            }
            insure_policy = insure_policies[0]
            if insure_policy.policy.creation_date:
                policy_date = datetime.datetime.strptime(str(insure_policy.policy.creation_date), "%Y-%m-%d")
                policy_date_str = policy_date.strftime("%d/%m/%Y")
                # data["dateEmission"] = str(policy_date_str)
                expiry_date = insure_policy.policy.creation_date + core.datetimedelta(years=5)
                new_expiry_date = datetime.datetime.strptime(str(expiry_date), "%Y-%m-%d")
                expiry_date_str = new_expiry_date.strftime("%d/%m/%Y")
                # jour = str(expiry_date_str).split("/")[0]
                # mois = str(expiry_date_str).split("/")[1]
                # annee = str(expiry_date_str).split("/")[2]
                # mois = my_dict.get(mois)
                data["DateExpiration"] = str(expiry_date_str)
        # Create qr code instance
        qr = qrcode.QRCode()
        # The data that you want to store
        # Add data
        qr.add_data({"CHFID: " + str(data["chfid"])})

        # Generate the QR Code
        qr.make()

        # Create an image from the QR Code instance
        img = qr.make_image(fill_color="white", back_color="transparent")

        # Create a BytesIO object
        buffered = BytesIO()

        # Save the image to the BytesIO object
        img.save(buffered, format="png")

        # Get the byte data
        img_str = base64.b64encode(buffered.getvalue())
        #img_encoded = base64.b64encode(img.getvalue())
        data["qrcode"] = "data:image/PNG;base64,"+img_str.decode("utf-8")
        insurees_data.append(data)
    dictBase =  {
        "datasource": insurees_data
    }
    print(dictBase)
    return dictBase


class PrintedReportsHistory(models.Model):
    """ Class PrintedReportsHistory :
    Class for reports already printed
    """
    id = models.AutoField(db_column='ID', primary_key=True)
    seq = models.CharField(db_column='Sequence', max_length=6)
    fosa = models.CharField(db_column='Fosa', max_length=248)
    start_date = models.CharField(db_column='startDate', blank=True,
                                  max_length=100, null=True)
    end_date = models.CharField(db_column='endDate',
                                max_length=100, blank=True, null=True)

    class Meta:
        db_table = "tblPrintedReportsHistory"

def format_services(claim_services):
    services = []
    for service in claim_services:
        service_strings = []
        
        if service.service and service.service.code:
            service_strings.append(f"Code: {service.service.code}")
        if service.service and service.service.name:
            service_strings.append(f"Nom: {service.service.name}")
        if service.service and service.service.price:
            service_strings.append(f"Prix: {float(service.service.price):.2f} KMF")
        if service.qty_provided:
            service_strings.append(f"Qte fournie: {float(service.qty_provided):.2f}")
        if service.price_asked:
            service_strings.append(f"Prix demande: {float(service.price_asked):.2f} KMF")
        # if service.qty_approved:
            # service_strings.append(f"Qté approuvée: {float(service.qty_approved):.2f}")
        # if service.price_approved:
            # service_strings.append(f"Prix approuvé: {float(service.price_approved):.2f}")
        if service.price_valuated:
            service_strings.append(f"Prix evalue: {float(service.price_valuated):.2f} KMF")
        # if service.price_adjusted:
            # service_strings.append(f"Prix ajusté: {float(service.price_adjusted):.2f}")
        # Joindre tous les éléments avec un séparateur
        service_data = " - ".join(service_strings) if service_strings else ""
        services.append(service_data) 
    service_merged="               | ".join(services) if services else ""
    return service_merged

def format_items(claim_items):
    items = []
    for item in claim_items:
        item_strings = []
        
        if item.item and item.item.code:
            item_strings.append(f"Code: {item.item.code}")
        if item.item and item.item.name:
            item_strings.append(f"Nom: {item.item.name}")
        if item.item and item.item.price:
            item_strings.append(f"Prix: {float(item.item.price):.2f} KMF")
        if item.qty_provided:
            item_strings.append(f"Qte fournie: {float(item.qty_provided):.2f}")
        if item.price_asked:
            item_strings.append(f"Prix demande: {float(item.price_asked):.2f} KMF")
        # if item.qty_approved:
            # item_strings.append(f"Qté approuvée: {float(item.qty_approved):.2f}")
        # if item.price_approved:
            # item_strings.append(f"Prix approuvé: {float(item.price_approved):.2f}")
        if item.price_valuated:
            item_strings.append(f"Prix value: {float(item.price_valuated):.2f} KMF")
        # if item.price_adjusted:
            # item_strings.append(f"Prix ajusté: {float(item.price_adjusted):.2f}")
        
        # Joindre tous les éléments avec un séparateur
        item_data = " - ".join(item_strings) if item_strings else ""
        items.append(item_data) 
    item_merged="               | ".join(items) if items else ""
    return item_merged

def report_prescriber_query(user, **kwargs):
    """
    Génère un rapport listant les prestations par prescripteur avec :
    - Nombre de prestations par prescripteur
    - Répartition par type d'acte (services et produits médicaux)
    - Répartition par période et par FOSA
    """
    print("Rapport Par Prescripteur", kwargs)
    
    # Récupération des paramètres
    prescriber_uuid = kwargs.get("prescriber_uuid")
    authorized_health_facilities_param = kwargs.get("authorized_health_facilities") 
    date_start = kwargs.get("date_start")
    date_end = kwargs.get("date_end")
    
    if not all([prescriber_uuid, date_start, date_end]):
        print("Paramètres manquants pour le rapport prescripteur")
        return {}
    
    # Conversion des dates
    date_from_object = datetime.datetime.strptime(date_start, "%Y-%m-%d")
    date_to_object = datetime.datetime.strptime(date_end, "%Y-%m-%d")
    
    # Récupération des informations de base
    try:
        
        # Récupération du prescripteur
        prescriber = Prescriber.objects.filter(
            uuid=prescriber_uuid,
            validity_to__isnull=True
        ).first()
        
        if not prescriber:
            print("Prescripteur non trouvé")
            return {}
        
        health_facilities = HealthFacility.objects.all()          
        if authorized_health_facilities_param:
            if isinstance(authorized_health_facilities_param, str):
                try:
                    authorized_health_facilities_ids = [
                        int(hf_id.strip()) 
                        for hf_id in authorized_health_facilities_param.split(',') 
                        if hf_id.strip().isdigit()
                    ]
                except ValueError as e:
                    print(f"Erreur de conversion des IDs FOSA: {e}")
                    authorized_health_facilities_ids = []
            elif isinstance(authorized_health_facilities_param, list):
                authorized_health_facilities_ids = authorized_health_facilities_param
            else:
                authorized_health_facilities_ids = []
            
            if authorized_health_facilities_ids:
                health_facilities = HealthFacility.objects.filter(
                    id__in=authorized_health_facilities_ids,
                    validity_to__isnull=True
                )
                print(f"FOSA autorisées filtrées: {authorized_health_facilities_ids}")
        else:
            health_facilities=prescriber.authorized_health_facilities.all()
        health_facilities_tostring_array = [
            {
                "hf_name": f"{hf.name} - {hf.code}",
            }
            for hf in health_facilities
        ]
        
        # Requête principale pour récupérer les claims du prescripteur
        claims = Claim.objects.filter(
            prescriber=prescriber,
            health_facility__in=health_facilities,
            date_from__gte=date_from_object,
            date_to__lte=date_to_object,
        )

        # Données de base du rapport
        today = datetime.datetime.now()
        final_data = {
            "prescriber_name": f"{prescriber.last_name} {prescriber.other_names}".strip(),
            "prescriber_code": prescriber.code,
            "prescriber_speciality": f"{prescriber.speciality.code} - {prescriber.speciality.speciality}".strip(),
            "main_health_facility": prescriber.main_health_facility,
            "authorized_health_facilities": health_facilities_tostring_array,
            "entry_date": prescriber.entry_date,
            "release_date": prescriber.release_date,
            "date_start": date_start,
            "date_end": date_end,
            "generation_date": today.strftime("%d/%m/%Y"),
            "generated_by": user.username if hasattr(user, 'username') else 'Système'
        }
        
        # Initialisation des compteurs
        sum_prestations_initiated = claims.filter(validity_to__isnull=True).count()
        sum_prestations_rejected = claims.filter(status=Claim.STATUS_REJECTED, validity_to__isnull=True).count()
        sum_prestations_validated = claims.filter(status=Claim.STATUS_VALUATED, validity_to__isnull=True).count()
        nb_person_refered = claims.filter(validity_to__isnull=True).distinct('insuree').count()

        ratio_validated = (sum_prestations_validated / sum_prestations_initiated * 100) if sum_prestations_initiated > 0 else 0
        ratio_rejected = (sum_prestations_rejected / sum_prestations_initiated * 100) if sum_prestations_initiated > 0 else 0

        final_data["sum_prestations_initiated"] = f"{sum_prestations_initiated:,}".replace(",", ".")
        final_data["sum_prestations_validated"] = f"{sum_prestations_validated:,}".replace(",", ".")
        final_data["sum_prestations_rejected"] = f"{sum_prestations_rejected:,}".replace(",", ".")
        final_data["nb_person_refered"] = f"{nb_person_refered:,}".replace(",", ".")
        final_data["ratio_validated"] = f"{round(ratio_validated, 2)} %"
        final_data["ratio_rejected"] = f"{round(ratio_rejected, 2)} %"


    
        claims_filtered = claims.filter(validity_to__isnull=True)
        if claims_filtered.count()==0:
            final_data["error"]="PAS DE PRESTATIONS DURANT CETTE PERIODE"
            final_data["claims"]=[]
            return json.loads(json.dumps(final_data, default=str))
        
        claims_serialized = []
        
        for claim in claims_filtered:
            claim_data = {
                "insuree_name": f"{claim.insuree.other_names} {claim.insuree.last_name}" if claim.insuree else "",
                "insuree_code": claim.insuree.chf_id if claim.insuree else "",
                "code": claim.code,
                "date_from": claim.date_from.isoformat() if claim.date_from else "",
                "date_to": claim.date_to.isoformat() if claim.date_to else "",
                "status_display": get_claim_status_display(claim.status,claim.rejection_reason),
                "claimed": f"{float(claim.claimed)}" if claim.claimed else "0",
                "approved": f"{float(claim.approved)}" if claim.approved else "0",
                "date_claimed": claim.date_claimed.isoformat() if claim.date_claimed else "",
                "date_processed": claim.date_processed.isoformat() if claim.date_processed else "",
                "health_facility_name": claim.health_facility.name if claim.health_facility else "",
                "health_facility_code": claim.health_facility.code if claim.health_facility else "",
                "icd_code": claim.icd.code if claim.icd else "",
                "icd_name": claim.icd.name if claim.icd else "",
                "services": format_services(claim.services.all()),  # Maintenant un tableau de strings
                "itemlist": format_items(claim.items.all())  # Maintenant un tableau de strings
            }
            claims_serialized.append(claim_data)
        
        final_data["claims"] = claims_serialized
        
        print(f"Nombre de claims trouvés: {len(claims_serialized)}")
        print(f"FOSA utilisées: {[hf['hf_name'] for hf in health_facilities_tostring_array]}")
        
        final_data_serializable = json.loads(json.dumps(final_data, default=str))
        print(final_data_serializable)
        
        return final_data_serializable
        
    except Exception as e:
        print(f"Erreur lors de la génération du rapport prescripteur: {e}")
        traceback.print_exc()
        return {}


def report_cotisation_query(user, **kwargs):
    date_start = kwargs.get("date_start")
    date_end = kwargs.get("date_end")

    date_from_object = datetime.datetime.strptime(date_start, "%Y-%m-%d")
    date_to_object = datetime.datetime.strptime(date_end, "%Y-%m-%d")

    policies=Policy.objects.all().filter(date_from__gte=date_from_object,
            date_to__lte=date_to_object,polygamous=False)
    print("policies", policies.count())
    families=policies.family
    nbMenageTotal=families.distinct().count()
    print("families", nbMenageTotal)
    nbBenefificaire=Insuree.objects.all().filter(family_in=families).count()
    print ("nbBenefificaire", nbBenefificaire)
    total_cotisation_attendues=0
    total_cotisation_persues=0
    solde_cotisation_attendues=0
    total_subvention=0
    for policy in policies:
        po=policy_values(policy,policy.family,policy,user)
        total_cotisation_attendues+=po.amount
    contributions=Premium.objects.all().filter(
        policy__in=policies,validity_to__isnull=True)
    for contribution in contributions:
        if contribution.payer is None:
            total_cotisation_persues=+contribution.amount
        else:
            total_subvention+=contribution.amount
    solde_cotisation_attendues=total_cotisation_attendues-total_cotisation_persues
    dictBase =  {
        "nbMenageTotal": nbMenageTotal,
        "nbBenefificaire": nbBenefificaire.count(),
        "total_cotisation_attendues": total_cotisation_attendues,
        "total_cotisation_persues": total_cotisation_persues,
        "solde_cotisation_attendues": solde_cotisation_attendues,
        "total_subvention": total_subvention,
    }
    print(dictBase)
    final_data_serializable= json.loads(json.dumps(dictBase, default=str))
    print(final_data_serializable)

    return final_data_serializable



    
    


def get_most_frequent_category(claims):
    """
    Returns the most frequent service category among the given claims.
    """
    categories = []
    for claim in claims:
        categories.extend([s.service.category for s in claim.services.all() if s.service.category])
    if not categories:
        return None
    return Counter(categories).most_common(1)[0][0]


def get_most_frequent_item_type(claims):
    """
    Returns the most frequent item type among the given claims.
    """
    types = []
    for claim in claims:
        types.extend([i.item.type for i in claim.items.all() if i.item.type])
    if not types:
        return None
    return Counter(types).most_common(1)[0][0]



def most_active_prescriber_func(claims):
    if not claims.exists():
        return None
    prescriber_counts = Counter(claim.prescriber_id for claim in claims if claim.prescriber_id)
    if not prescriber_counts:
        return None
    most_active_id, _ = prescriber_counts.most_common(1)[0]
    return claims.filter(prescriber_id=most_active_id).first().prescriber


def report_fosa_prescriber_query(user, **kwargs):
    """
    Génère un rapport listant les prescripteurs et leur volume de prestation.
    """


    print("Rapport Par Prescripteur", kwargs)

    # Paramètres obligatoires
    hf_uuid = kwargs.get("hf_uuid")
    date_start = kwargs.get("date_start")
    date_end = kwargs.get("date_end")

    if not all([hf_uuid, date_start, date_end]):
        print("Paramètres manquants pour le rapport prescripteur")
        return {}

    # Paramètres facultatifs
    speciality_uuid = kwargs.get("speciality_uuid")
    if speciality_uuid == "null" or speciality_uuid =="undefined":
        speciality_uuid=None
    prescriber_status_code = kwargs.get("prescriber_status_code")
    if prescriber_status_code == "null" or prescriber_status_code =="undefined":
        prescriber_status_code=None
    act_type = kwargs.get("act_type")  # 1: article, 2: service
    if act_type == "null" or act_type =="undefined":
        act_type=None
    claim_status = kwargs.get("claim_status")
    if claim_status == "null" or claim_status =="undefined":
        claim_status=None

    date_from_object = datetime.datetime.strptime(date_start, "%Y-%m-%d")
    date_to_object = datetime.datetime.strptime(date_end, "%Y-%m-%d")

    try:
        speciality = Speciality.objects.filter(validity_to__isnull=True, uuid=speciality_uuid).first()
        status = Status.objects.filter(code=prescriber_status_code).first()
        hf = HealthFacility.objects.filter(uuid=hf_uuid, validity_to__isnull=True).first()

        prescribers = Prescriber.objects.all()
        if speciality:
            prescribers = prescribers.filter(speciality=speciality)
        if status:
            prescribers = prescribers.filter(status=status)
        if hf:
            prescribers = prescribers.filter(
                Q(main_health_facility=hf) | Q(authorized_health_facilities=hf)
            )

        # Liste complète de claims
        claims = Claim.objects.filter(
            validity_to__isnull=True,
            prescriber__in=prescribers,
            health_facility=hf,
            date_from__gte=date_from_object,
            date_to__lte=date_to_object,
        )

        # Liste filtrée si on impose un statut
        claims_filtered = claims
        if claim_status and claim_status != "null":
            claims_filtered = claims.filter(status=claim_status)


        active_prescribers = Prescriber.objects.filter(
            id__in=claims_filtered.values_list("prescriber_id", flat=True),
        ).distinct()

        prescriber_stats = []

        total_active_prescriber=active_prescribers.count()
        total_claim_initated=claims.count()

        total_claim_rejected = claims.filter(status=Claim.STATUS_REJECTED).count()

        average_FOSA_rejection_rate=((total_claim_rejected / total_claim_initated) * 100
                if total_claim_initated > 0 else 0)
        
        sum_montant_reclame=0
        sum_montant_valide=0

        most_active_prescriber=most_active_prescriber_func(claims_filtered)
        most_active_prescriber_info=f"{most_active_prescriber.code} - {most_active_prescriber.last_name} {most_active_prescriber.other_names} - {most_active_prescriber.nin}" if most_active_prescriber else ""



        for prescriber in active_prescribers:
            prescriber_claims = claims.filter(prescriber=prescriber)
            prescriber_claims_filtered = claims_filtered.filter(prescriber=prescriber)

            nb_prestations_initiees = prescriber_claims.count()
            nb_prestations_rejetees = prescriber_claims.filter(status=Claim.STATUS_REJECTED).count()
            ratio_rejection = (
                (nb_prestations_rejetees / nb_prestations_initiees) * 100
                if nb_prestations_initiees > 0 else 0
            )

            # Ajustement selon le type d'acte demandé
            if act_type and act_type != "null" and act_type!="undefined":
                for claim_p in prescriber_claims:
                    if act_type == '1':  # service uniquement
                        services_list = claim_p.services.all()
                        montant_service_asked = sum(
                            (s.qty_provided) * (s.price_asked or 0) for s in services_list
                        )
                        montant_service_valuated = sum(
                            (s.qty_provided) * (s.price_valuated or 0) for s in services_list
                        )
                        claim_p.claimed = montant_service_asked
                        claim_p.approved = montant_service_valuated

                    elif act_type == '2':  # article uniquement
                        items = claim_p.items.all()
                        montant_item_asked = sum(
                            (i.qty_provided) * (i.price_asked or 0) for i in items
                        )
                        montant_item_valuated = sum(
                            (i.qty_provided) * (i.price_valuated or 0) for i in items
                        )
                        claim_p.claimed = montant_item_asked
                        claim_p.approved = montant_item_valuated

            montant_reclame = sum((c.claimed or 0) for c in prescriber_claims)
            montant_valide = sum((c.approved or 0) for c in prescriber_claims)
            sum_montant_reclame+=montant_reclame
            sum_montant_valide+=montant_valide

            ratio_approbation = (
                (montant_valide / montant_reclame) * 100 if montant_reclame > 0 else 0
            )

            # Analyse sur claims filtrés
            category_service_dominant = get_most_frequent_category(prescriber_claims_filtered)
            item_type_dominant = get_most_frequent_item_type(prescriber_claims_filtered)

            dominant=""
            if act_type == '1':
                dominant = get_service_category_display(category_service_dominant)
            elif act_type == '2':
                dominant = get_item_type_display(item_type_dominant)
            else:
                dominant = (
                    f"Categorie service: {get_service_category_display(category_service_dominant)} "
                    f"- Type article: {get_item_type_display(item_type_dominant)}"
                )

            latest_claim = prescriber_claims_filtered.order_by("-date_claimed").first()
            last_prestation_date = latest_claim.date_claimed if latest_claim else None

            stats = {
                "prescriber": f"{prescriber.code} - {prescriber.last_name} {prescriber.other_names} - {prescriber.nin}".strip(),
                "prescriber_speciality": f"{prescriber.speciality.code} - {prescriber.speciality.speciality}".strip(),
                "nb_prestations_initiees": f"{nb_prestations_initiees}",
                "nb_prestations_rejetees": f"{nb_prestations_rejetees}",
                "ratio_rejection": f"{float(ratio_rejection)}%",
                "montant_reclame": f"{montant_reclame} KMF",
                "montant_valide": f"{montant_valide} KMF",
                "ratio_approbation": f"{ratio_approbation:.2f}%",
                "dominant": dominant,
                "last_prestation_date": str(last_prestation_date) if last_prestation_date else None,
            }

            prescriber_stats.append(stats)


       
        
        abs_diff=abs(sum_montant_reclame-sum_montant_valide)

        
        final_data={
            "hf_detail":f"{hf.code} - {hf.name}",
            "date_from":f"{date_start}",
            "date_to":f"{date_start}",
            "speciality_prescriber": f"{speciality.code} - {speciality.speciality}" if speciality else "Tous",
            "status_prescriber":f"{status.code} - {status.status}" if status else "Tous",
            "claim_status":get_claim_status_display(claim_status,None) if claim_status  else "Tous",
            "act_type":get_act_type_display(act_type) if act_type  else "Tous",
            "total_active_prescriber":f"{total_active_prescriber}",
            "total_presation_initie":f"{total_claim_initated} ",
            "total_prestation_rejete":f"{total_claim_rejected} ",
            "ratio_rejection":f"{float(average_FOSA_rejection_rate)} %",
            "montant_asked":f"{float(sum_montant_reclame)} KMF",
            "montant_validated":f"{float(sum_montant_valide)} KMF",
            "abs_diff":f"{float(abs_diff)} KMF" if abs_diff else "0 KMF",
            "most_active_prescriber":f"{most_active_prescriber_info}" if most_active_prescriber else "",
            "prescriber_stats":prescriber_stats
        }

        if len(prescriber_stats)==0:
            final_data["error"]="PAS DE PRESTATIONS DURANT CETTE PERIODE"
        
        # Retourne toute la liste, pas juste le dernier élément
        final_data_serializable= json.loads(json.dumps(final_data, default=str))
        print(final_data_serializable)

        return final_data_serializable

    except Exception as e:
        traceback.print_exc()
        print(f"Erreur lors de la génération du rapport prescripteur: {e}")
        return {}


def invoice_private_fosa_query(user, **kwargs):
    print("Rapport Par FOSA ", kwargs)
    date_from = kwargs.get("date_from")
    date_to = kwargs.get("date_to")
    format = "%Y-%m"
    hflocation = kwargs.get("hflocation")

    date_from_object = datetime.datetime.strptime(date_from, format)
    date_from_str = date_from_object.strftime("%Y/%m")

    date_to_object = datetime.datetime.strptime(date_to, format)
    days_in_month = calendar.monthrange(date_to_object.year, date_to_object.month)[1]
    date_to_str = date_to_object.strftime("%Y/%m")
    report_fetch = PrintedReportsHistory.objects.filter(
        start_date=date_from,
        end_date=date_to,
        fosa=hflocation
    )
    print("report_fetch ", report_fetch)
    if report_fetch:
        numero_facture = report_fetch[0].seq
        print("Exitant ", numero_facture)
    else:
        print("Non exitant")
        report_max_seq = PrintedReportsHistory.objects.filter(
            fosa=hflocation
        ).order_by('-seq').first()
        prochain = 1
        if report_max_seq:
            prochain = int(report_max_seq.seq) + 1
        numero_facture = "{:0>6}".format(str(prochain))
        PrintedReportsHistory.objects.create(
            **{
                "seq": "{:0>6}".format(str(prochain)),
                "fosa": hflocation,
                "start_date": date_from,
                "end_date": date_to
            }
        )
    invoice_data = []
    dictGeo = {}
    grand_total = 0
    today = datetime.datetime.now()
    today_date = str(today).split(" ")[0]
    final_data =  {}
    final_data["jour"] = today_date.split("-")[2]
    final_data["mois"] = today_date.split("-")[1]
    final_data["annee"] = today_date.split("-")[0]
    my_dict = {
        "01": "Janvier",
        "02": "Février",
        "03": "Mars",
        "04": "Avril",
        "05": "Mai",
        "06": "Juin",
        "07": "Juillet",
        "08": "Août",
        "09": "Septembre",
        "10": "Octobre",
        "11": "Novembre",
        "12": "Décembre"
    }
    final_data["moisReleve"] = my_dict.get(date_from.split("-")[1])
    # Get the district
    if hflocation and hflocation!="0" :
        # P, C: Pricate and Charity Health facilities
        hflocationObj = HealthFacility.objects.filter(
            code=hflocation,
            legal_form__code__in=['P', 'C'],
            validity_to__isnull=True
        ).first()
        if hflocationObj:
            final_data["noReleve"] = hflocationObj.code + "/" + str(numero_facture)
            dictGeo['health_facility'] = hflocationObj.id
            level_village = False
            level_district = False
            level_ville = False
            municipality = " "
            district = " "
            village = " "
            region = " "
            if hflocationObj.location.parent:
                level_district = True
                if hflocationObj.location.parent.parent:
                    level_ville = True
                    if hflocationObj.location.parent.parent.parent:
                        level_village = True
            if level_village:
                village = hflocationObj.location.name
                municipality = hflocationObj.location.parent.name
                district = hflocationObj.location.parent.parent.code
                region = hflocationObj.location.parent.parent.parent.code
            elif level_ville:
                municipality = hflocationObj.location.name
                district = hflocationObj.location.parent.code
                region = hflocationObj.location.parent.parent.code
            elif level_district:
                district = hflocationObj.location.code
                region = hflocationObj.location.parent.code
            else:
                region = hflocationObj.location.code
            final_data["RegionCode"] = region
            final_data["CodeDistrict"] = district
            final_data["Structure"] = hflocationObj.name
            final_data["CodeStructure"] = hflocationObj.code
            status_excluded = [1, 2]
            claim_list = Claim.objects.exclude(
                status__in=status_excluded
            ).filter(
                date_to__gte=date_from + "-01", # Premier jour de la période
                date_to__lte=date_to + "-" + str(days_in_month), #Dernier jour de la période
                validity_to__isnull=True,
                health_facility_id=hflocationObj.id
            )
            i = 1
            for claim in claim_list:
                data = {}
                chfid2 = ""
                chfid1 = claim.insuree.chf_id
                if claim.insuree.family:
                    members = Insuree.objects.filter(
                        family_id=claim.insuree.family.id,
                        validity_to__isnull=True
                    ).exclude(id=claim.insuree.id)
                    mother_ok = False
                    for membre in members:
                        if membre.relationship:
                            if str(membre.relationship.relation).lower() in ["spouse", "époux"]:
                                chfid2 = membre.chf_id
                                mother_ok = True
                            if mother_ok:
                                break
                data["chfid"] = chfid1
                data["chfidbenef"] = chfid2
                if claim.insuree.family:
                    if claim.insuree.family.parent:
                        # We exchange the head and the spouse
                        data["chfid"] = chfid2
                        data["chfidbenef"] = chfid1
                if data["chfidbenef"] == "":
                    data["chfidbenef"] = data["chfid"]
                data["row_number"] = str(i)
                data["fpce"] = claim.code
                
                invoice_data.append(data)
                claim_service = ClaimService.objects.filter(
                    claim = claim,
                    status=1
                )
                total_service_amount = 0
                for claim_service_elmt in claim_service:
                    if claim_service_elmt.price_valuated:
                        total_service_amount+=claim_service_elmt.price_valuated
                    elif claim_service_elmt.price_approved:
                        total_service_amount+=claim_service_elmt.price_approved
                    elif claim_service_elmt.price_adjusted:
                        total_service_amount+=claim_service_elmt.price_adjusted
                    elif claim_service_elmt.price_asked:
                        total_service_amount+=claim_service_elmt.price_asked
                
                claim_items = ClaimItem.objects.filter(
                    claim = claim,
                    status=1
                )
                total_item_amount = 0
                for claim_item_elmt in claim_items:
                    if claim_item_elmt.price_valuated:
                        total_item_amount+=claim_item_elmt.price_valuated
                    elif claim_item_elmt.price_approved:
                        total_item_amount+=claim_item_elmt.price_approved
                    elif claim_item_elmt.price_adjusted:
                        total_item_amount+=claim_item_elmt.price_adjusted
                    elif claim_item_elmt.price_asked:
                        total_item_amount+=claim_item_elmt.price_asked
                somme = total_service_amount+total_item_amount
                data["amount"] = str("{:,.0f}".format(float(somme)))
                i+=1
                grand_total += somme
    final_data["total"] = str("{:,.0f}".format(float(grand_total))) + " KMF"
    empty_data = []
    empty_data.append({"text2": "\n\n\n\n\n"})
    final_data["data2"] = empty_data
    final_data["data"] = invoice_data
    
    print("\n\n\n\n\n")
    print(final_data)
    return final_data


def invoice_public_fosa_query(user, **kwargs):
    print("Rapport Par FOSA ", kwargs)
    date_from = kwargs.get("date_from")
    date_to = kwargs.get("date_to")
    format = "%Y-%m"
    hflocation = kwargs.get("hflocation")

    date_from_object = datetime.datetime.strptime(date_from, format)
    date_from_str = date_from_object.strftime("%Y/%m")

    date_to_object = datetime.datetime.strptime(date_to, format)
    days_in_month = calendar.monthrange(date_to_object.year, date_to_object.month)[1]
    date_to_str = date_to_object.strftime("%Y/%m")
    report_fetch = PrintedReportsHistory.objects.filter(
        start_date=date_from,
        end_date=date_to,
        fosa=hflocation
    )
    print("report_fetch ", report_fetch)
    if report_fetch:
        numero_facture = report_fetch[0].seq
        print("Exitant ", numero_facture)
    else:
        print("Non exitant")
        report_max_seq = PrintedReportsHistory.objects.filter(
            fosa=hflocation
        ).order_by('-seq').first()
        prochain = 1
        if report_max_seq:
            prochain = int(report_max_seq.seq) + 1
        numero_facture = "{:0>6}".format(str(prochain))
        PrintedReportsHistory.objects.create(
            **{
                "seq": "{:0>6}".format(str(prochain)),
                "fosa": hflocation,
                "start_date": date_from,
                "end_date": date_to
            }
        )
    invoice_data = []
    dictGeo = {}
    grand_total = 0
    today = datetime.datetime.now()
    today_date = str(today).split(" ")[0]
    final_data =  {}
    final_data["jour"] = today_date.split("-")[2]
    final_data["mois"] = today_date.split("-")[1]
    final_data["annee"] = today_date.split("-")[0]
    my_dict = {
        "01": "Janvier",
        "02": "Février",
        "03": "Mars",
        "04": "Avril",
        "05": "Mai",
        "06": "Juin",
        "07": "Juillet",
        "08": "Août",
        "09": "Septembre",
        "10": "Octobre",
        "11": "Novembre",
        "12": "Décembre"
    }
    final_data["moisReleve"] = my_dict.get(date_from.split("-")[1])
    # P, C: Pricate and Charity Health facilities
    if hflocation and hflocation!="0" :
        hflocationObj = HealthFacility.objects.filter(
            code=hflocation,
            validity_to__isnull=True
        ).exclude(legal_form__code__in=['P', 'C']).first()
        if hflocationObj:
            final_data["noReleve"] = hflocationObj.code + "/" + str(numero_facture)
            dictGeo['health_facility'] = hflocationObj.id
            level_village = False
            level_district = False
            level_ville = False
            municipality = " "
            district = " "
            village = " "
            region = " "
            if hflocationObj.location.parent:
                level_district = True
                if hflocationObj.location.parent.parent:
                    level_ville = True
                    if hflocationObj.location.parent.parent.parent:
                        level_village = True
            if level_village:
                village = hflocationObj.location.name
                municipality = hflocationObj.location.parent.name
                district = hflocationObj.location.parent.parent.code
                region = hflocationObj.location.parent.parent.parent.code
            elif level_ville:
                municipality = hflocationObj.location.name
                district = hflocationObj.location.parent.code
                region = hflocationObj.location.parent.parent.code
            elif level_district:
                district = hflocationObj.location.code
                region = hflocationObj.location.parent.code
            else:
                region = hflocationObj.location.code
            final_data["RegionCode"] = region
            final_data["CodeDistrict"] = district
            final_data["Structure"] = hflocationObj.name
            final_data["CodeStructure"] = hflocationObj.code
            status_excluded = [1, 2]
            claim_list = Claim.objects.exclude(
                status__in=status_excluded
            ).filter(
                date_to__gte=date_from + "-01", # Premier jour de la période
                date_to__lte=date_to + "-" + str(days_in_month), #Dernier jour de la période
                validity_to__isnull=True,
                health_facility_id=hflocationObj.id
            )
            i = 1
            for claim in claim_list:
                data = {}
                chfid2 = ""
                chfid1 = claim.insuree.chf_id
                if claim.insuree.family:
                    members = Insuree.objects.filter(
                        family_id=claim.insuree.family.id,
                        validity_to__isnull=True
                    ).exclude(id=claim.insuree.id)
                    mother_ok = False
                    for membre in members:
                        if membre.relationship:
                            if str(membre.relationship.relation).lower() in ["spouse", "époux"]:
                                chfid2 = membre.chf_id
                                mother_ok = True
                            if mother_ok:
                                break
                data["chfid"] = chfid1
                data["chfidbenef"] = chfid2
                if claim.insuree.family:
                    if claim.insuree.family.parent:
                        # We exchange the head and the spouse
                        data["chfid"] = chfid2
                        data["chfidbenef"] = chfid1
                if data["chfidbenef"] == "":
                    data["chfidbenef"] = data["chfid"]
                data["row_number"] = str(i)
                data["fpce"] = claim.code
                
                invoice_data.append(data)
                claim_service = ClaimService.objects.filter(
                    claim = claim,
                    status=1
                )
                total_service_amount = 0
                for claim_service_elmt in claim_service:
                    if claim_service_elmt.price_valuated:
                        total_service_amount+=claim_service_elmt.price_valuated
                    elif claim_service_elmt.price_approved:
                        total_service_amount+=claim_service_elmt.price_approved
                    elif claim_service_elmt.price_adjusted:
                        total_service_amount+=claim_service_elmt.price_adjusted
                    elif claim_service_elmt.price_asked:
                        total_service_amount+=claim_service_elmt.price_asked
                
                claim_items = ClaimItem.objects.filter(
                    claim = claim,
                    status=1
                )
                total_item_amount = 0
                for claim_item_elmt in claim_items:
                    if claim_item_elmt.price_valuated:
                        total_item_amount+=claim_item_elmt.price_valuated
                    elif claim_item_elmt.price_approved:
                        total_item_amount+=claim_item_elmt.price_approved
                    elif claim_item_elmt.price_adjusted:
                        total_item_amount+=claim_item_elmt.price_adjusted
                    elif claim_item_elmt.price_asked:
                        total_item_amount+=claim_item_elmt.price_asked
                somme = total_service_amount+total_item_amount
                data["amount"] = str("{:,.0f}".format(float(somme)))
                i+=1
                grand_total += somme
    final_data["total"] = str("{:,.0f}".format(float(grand_total))) + " KMF"
    empty_data = []
    empty_data.append({"text2": "\n\n\n\n\n"})
    final_data["data2"] = empty_data
    final_data["data"] = invoice_data
    print(final_data)
    return final_data




def report_membership_query(user, **kwargs):
    print("Rapport adhesion ", kwargs)
    ids = kwargs.get("familyID", [])
    family_ids = []
    if ids:
        ids = ids.split(',')
        family_ids = [eval(i) for i in ids]
    family_list = Family.objects.filter(
        id__in=family_ids,
        validity_to__isnull=True
    )
    data = []
    data2 = []
    dictbase = {}
    print("family_list ", family_list)
    if family_list:
        for family in family_list:
            row = 1
            encoded_img = False
            dictbase["headDigit1"] = " "
            dictbase["headDigit2"] = " "
            dictbase["headDigit3"] = " "
            dictbase["headDigit4"] = " "
            dictbase["headDigit5"] = " "
            dictbase["headDigit6"] = " "
            dictbase["headDigit7"] = " "

            dictbase["headDigit1"] = " "
            dictbase["headDigit2"] = " "
            dictbase["headDigit3"] = " "
            dictbase["headDigit4"] = " "
            dictbase["headDigit5"] = " "
            dictbase["headDigit6"] = " "
            dictbase["headDigit7"] = " "
            dictbase["email"] = " "
            
            head = family.head_insuree
            if head and head.email:
                dictbase["email"] = head.email
            print("chec ", head.profession)
            dictbase["familyType"] = " "
            dictbase["profession"] = " "
            maritals = {
                "1": "reportcomores.marital.maried",
                "2": "reportcomores.marital.polygamous",
                "3": "reportcomores.marital.divorced",
                "4": "reportcomores.marital.widowed",
                "5": "reportcomores.marital.single"
            }
            old_maritals = {
                "M": "reportcomores.marital.maried",
                "P": "reportcomores.marital.polygamous",
                "D": "reportcomores.marital.divorced",
                "W": "reportcomores.marital.widowed",
                "S": "reportcomores.marital.single"
            }
            if head and head.marital:
                # Get translation in a specific language
                translated_text = False
                with override('fr_KM'):
                    value = maritals.get(str(head.marital), False)
                    if not value:
                        value = old_maritals.get(str(head.marital), False)
                    if value:
                        translated_text = _(value)
                        if translated_text:
                            dictbase["familyType"] = str(translated_text)
            if head and head.profession:
                dictbase["profession"] = head.profession.alt_language
            if family.location:
                hflocation_obj = Location.objects.filter(
                    id=family.location.id,
                    validity_to__isnull=True
                ).first()
                print("hflocation_obj ", hflocation_obj)
                if hflocation_obj:
                    level_village = False
                    level_district = False
                    level_ville = False
                    municipality = " "
                    district = " "
                    village = " "
                    region = " "
                    if hflocation_obj.parent:
                        level_district = True
                        if hflocation_obj.parent.parent:
                            level_ville = True
                            if hflocation_obj.parent.parent.parent:
                                level_village = True
                    if level_village:
                        village = hflocation_obj.name
                        municipality = hflocation_obj.parent.name
                        district = hflocation_obj.parent.parent.name
                        region = hflocation_obj.parent.parent.parent.name
                    elif level_ville:
                        municipality = hflocation_obj.name
                        district = hflocation_obj.parent.name
                        region = hflocation_obj.parent.parent.name
                    elif level_district:
                        district = hflocation_obj.name
                        region = hflocation_obj.parent.name
                    else:
                        region = hflocation_obj.location.name
                    dictbase["locality"] = village
                    if village != "":
                        dictbase["locality"] += ", " + district
                    else:
                        dictbase["locality"] = district
                    dictbase["region"] = region
                    dictbase["community"] = municipality
                    print("locality ", dictbase["locality"])
                    print(dictbase["region"])
                    print(dictbase["community"])
            if head and head.phone and len(head.phone) >= 7:
                if family.parent:
                    dictbase["ConjointDigit1"] = head.phone[0]
                    dictbase["ConjointDigit2"] = head.phone[1]
                    dictbase["ConjointDigit3"] = head.phone[2]
                    dictbase["ConjointDigit4"] = head.phone[3]
                    dictbase["ConjointDigit5"] = head.phone[4]
                    dictbase["ConjointDigit6"] = head.phone[5]
                    dictbase["ConjointDigit7"] = head.phone[6]
                else:
                    dictbase["headDigit1"] = head.phone[0]
                    dictbase["headDigit2"] = head.phone[1]
                    dictbase["headDigit3"] = head.phone[2]
                    dictbase["headDigit4"] = head.phone[3]
                    dictbase["headDigit5"] = head.phone[4]
                    dictbase["headDigit6"] = head.phone[5]
                    dictbase["headDigit7"] = head.phone[6]
            members = Insuree.objects.filter(
                family_id=family.id,
                validity_to__isnull=True
            ).exclude(id=head.id if head else 0)
            print("members ", members)
            for membre in members:
                print("relation ", membre.relationship)
                if membre.relationship:
                    jour = str(membre.dob).split("-")[2]
                    mois = str(membre.dob).split("-")[1]
                    annee = str(membre.dob).split("-")[0]
                    values = {}
                    if str(membre.relationship.relation).lower() in ["spouse", "époux"]:
                        values["numero"] = str(row)
                        values["libelle"] = "Conjoint(e)"
                        values["chfid"] = membre.chf_id
                        values["FirstName"] = membre.last_name
                        values["LastName"] = membre.other_names
                        values["dob"] = jour + "-" + mois + "-" + annee
                        if membre.gender:
                            values["sex"] = str(membre.gender.code)
                        if membre.phone and len(membre.phone) >= 7:
                            if family.parent:
                                dictbase["headDigit1"] = membre.phone[0]
                                dictbase["headDigit2"] = membre.phone[1]
                                dictbase["headDigit3"] = membre.phone[2]
                                dictbase["headDigit4"] = membre.phone[3]
                                dictbase["headDigit5"] = membre.phone[4]
                                dictbase["headDigit6"] = membre.phone[5]
                                dictbase["headDigit7"] = membre.phone[6]
                            else:
                                dictbase["ConjointDigit1"] = membre.phone[0]
                                dictbase["ConjointDigit2"] = membre.phone[1]
                                dictbase["ConjointDigit3"] = membre.phone[2]
                                dictbase["ConjointDigit4"] = membre.phone[3]
                                dictbase["ConjointDigit5"] = membre.phone[4]
                                dictbase["ConjointDigit6"] = membre.phone[5]
                                dictbase["ConjointDigit7"] = membre.phone[6]
                        data.append(values)
                    elif str(membre.relationship.relation).lower() in ["fils/fille", "son/daughter"]:
                        values["numero"] = str(row)
                        values["libelle"] = "Bénéficiaire"
                        values["chfid"] = membre.chf_id
                        values["FirstName"] = membre.last_name
                        values["LastName"] = membre.other_names
                        values["dob"] = jour + "-" + mois + "-" + annee
                        if membre.gender:
                            values["sex"] = str(membre.gender.code)
                        data.append(values)
                    else:
                        values2 = {}
                        values2["numero"] = str(row)
                        values2["libelle"] = "Bénéficiaire"
                        values2["chfid"] = membre.chf_id
                        values2["FirstName"] = membre.last_name
                        values2["LastName"] = membre.other_names
                        values2["dob"] = jour + "-" + mois + "-" + annee
                        if membre.gender:
                            values2["sex"] = str(membre.gender.code)
                        data2.append(values2)
                row += 1
            insure_policy = InsureePolicy.objects.filter(
                insuree=head.id if head else 0, validity_to__isnull=True
            ).order_by("-id")
            dictbase["total"] = " "
            dictbase["jour"] = " "
            dictbase["mois"] = " "
            dictbase["annee"] = " "
            if insure_policy:
                inspolicy  = insure_policy[0]
                policy = Policy.objects.filter(id=inspolicy.policy.id).first()
                if policy:
                    dictbase["total"] = str("{:,.0f}".format(float(policy.value))) + " KMF " + amount_to_text_fr(int(policy.value), 'KMF')
                    dictbase["jour"] = str(policy.start_date).split("-")[2]
                    dictbase["mois"] = str(policy.start_date).split("-")[1]
                    dictbase["annee"] = str(policy.start_date).split("-")[0]
                    contribution = policy.contribution_plan
                    if contribution:
                        if contribution.code in ["AMOE", "AMOG", "AMOS"]:
                            dictbase["amo"] = "x"
                        if contribution.code in ["AMOS1", "AMOS2", "AMOS3", "AMOS4"]:
                            dictbase["amos"] = "x"
                        if contribution.code in ["AMS"]:
                            dictbase["ams"] = "x"
                    if policy.payment_day:
                        if str(policy.payment_day) == "5":
                            dictbase["D5"] = "x"
                        if str(policy.payment_day) == "10":
                            dictbase["D10"] = "x"
                        if str(policy.payment_day) == "15":
                            dictbase["D15"] = "x"
                        if str(policy.payment_day) == "20":
                            dictbase["D20"] = "x"
                    premium = Premium.objects.filter(validity_to__isnull=True, policy_id=policy.id).first()
                    if premium:
                        if premium.pay_type == "B":
                            dictbase["Bank"] = "x"
                        if premium.pay_type == "M":
                            dictbase["Mobile"] = "x"
                        if premium.pay_type not in ["M", "B"]:
                            dictbase["Virement"] = "x"
                    if policy.periodicity:
                        if policy.periodicity == "M":
                            dictbase["M"] = "x"
                        if policy.periodicity == "Q":
                            dictbase["T"] = "x"
                        if policy.periodicity == "S":
                            dictbase["S"] = "x"
                        if policy.periodicity == "Y":
                            dictbase["A"] = "x"
            dictbase["immat"] = " "
            dictbase["firstName"] = " "
            dictbase["lastName"] = " "
            dictbase["address"] = " "
            if head:
                dictbase["immat"] = head.chf_id
                dictbase["firstName"] = head.last_name
                dictbase["lastName"] = head.other_names
                dictbase["address"] = family.address if family.address is not None else " "
            if head and head.gender:
                if head.gender.code == 'M':
                    dictbase["civiliteM"] = "x"
                    dictbase["civiliteF"] = ""
                if head.gender.code == 'F':
                    dictbase["civiliteF"] = "x"
                    dictbase["civiliteM"] = ""
            if head:
                if head.photo and head.photo.photo:
                    imageData = str(head.photo.photo)
                    myimage = base64.b64decode((imageData))
                    extension = imghdr.what(None, h=myimage)
                    print("extension ", extension)
                    if extension:
                        if str(extension).lower() != 'png':
                            # save image to png, image can have different format leading to an
                            # error :  image is not PNG
                            imgFile = open('/tmp/'+head.chf_id+'.jpeg', 'wb')
                            imgFile.write(myimage)
                            imgFile.close()

                            img1 = Image.open(r'/tmp/'+head.chf_id+'.jpeg')
                            img1.save(r'/tmp/'+head.chf_id+'.png')

                            with open('/tmp/'+head.chf_id+'.png', "rb") as image_file:
                                encoded_img = base64.b64encode(image_file.read()).decode('utf-8')
                        else:
                            # already the expected extension (PNG)
                            encoded_img = imageData
                else:
                    filename = ""
                    try:
                        filename = "openIMISphone/"+head.photo.folder+"/"+head.photo.filename
                    except Exception as e:
                        print(e)
                    print(filename)
                    if os.path.exists(filename):
                        with open(filename, "rb") as image_file:
                            imageData = base64.b64encode(image_file.read()).decode('utf-8')
                            myimage = base64.b64decode((imageData))
                            extension = imghdr.what(None, h=myimage)
                            print("extension is: ", extension)
                            if str(extension).lower() != 'png':
                                # save image to png, image can have different format leading to an
                                # error : image is not PNG
                                imgFile = open('/tmp/'+head.chf_id+'.jpeg', 'wb')
                                imgFile.write(myimage)
                                imgFile.close()

                                img1 = Image.open(r'/tmp/'+head.chf_id+'.jpeg')
                                img1.save(r'/tmp/'+head.chf_id+'.png')

                                with open('/tmp/'+head.chf_id+'.png', "rb") as image_file:
                                    encoded_img = base64.b64encode(image_file.read()).decode('utf-8')
                            else:
                                # already the expected extension (PNG)
                                encoded_img = imageData
                    # else:
                    #     with open("default-img.png", "rb") as image_file:
                    #         encoded_img = base64.b64encode(image_file.read()).decode('utf-8')
                    #     print("File not found")
            dictbase['data'] = data
            dictbase['data2'] = data2
            if encoded_img:
                dictbase["PhotoInsuree"] = "data:image/png;base64,"+str(encoded_img)
    print(dictbase)
    return dictbase