from django.db import models
from report.services import run_stored_proc_report
from insuree.models import Insuree, Family
import qrcode
from io import BytesIO
import base64, core, datetime
from insuree.models import InsureePolicy
import calendar
from location.models import Location, HealthFacility
from claim.models import Claim, ClaimService, ClaimItem
import random
from policy.models import Policy
import imghdr, os
from PIL import Image

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
        chef_menage = insuree_obj.last_name + " " + insuree_obj.other_names
        chfid = insuree_obj.chf_id
        if insuree_obj.family:
            members = Insuree.objects.filter(
                family_id=insuree_obj.family.id,
                validity_to__isnull=True
            ).exclude(id=insuree_obj.id)
            mother_ok = False
            for membre in members:
                if membre.relationship:
                    if str(membre.relationship.relation).lower() in ["spouse", "époux"]:
                        conjointe = membre.last_name + " " + membre.other_names
                        chfid2 = membre.chf_id
                        mother_ok = True
                    if mother_ok:
                        break
        chef_menage = chef_menage[:19] #19 Caracteres max
        conjointe = conjointe[:19] #19 Caracteres max
        data["FullFathersName"] = chef_menage
        data["FullMothersName"] = conjointe
        data["chfid"] = chfid
        data["chfid2"] = chfid2
        if insuree_obj.family:
            if insuree_obj.family.parent:
                # We exchange the head and the spouse
                data["FullFathersName"] = conjointe
                data["FullMothersName"] = chef_menage
                data["chfid"] = chfid2
                data["chfid2"] = chfid
        insure_policies = InsureePolicy.objects.filter(
            insuree=insuree_obj.id, policy__status=2).order_by('-id')
        data["DateExpiration"] = ""
        data["dateEmission"] = ""
        if insure_policies:
            insure_policy = insure_policies[0]
            if insure_policy.policy.creation_date:
                policy_date = datetime.datetime.strptime(str(insure_policy.policy.creation_date), "%Y-%m-%d")
                policy_date_str = policy_date.strftime("%d/%m/%Y")
                data["dateEmission"] = str(policy_date_str)
                expiry_date = insure_policy.policy.creation_date + core.datetimedelta(years=5)
                new_expiry_date = datetime.datetime.strptime(str(expiry_date), "%Y-%m-%d")
                expiry_date_str = new_expiry_date.strftime("%d/%m/%Y")
                data["DateExpiration"] = str(expiry_date_str)
        # Create qr code instance
        qr = qrcode.QRCode()
        # The data that you want to store
        # Add data
        qr.add_data({"CHFID: " + str(data["chfid"])})

        # Generate the QR Code
        qr.make()

        # Create an image from the QR Code instance
        img = qr.make_image()

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
    start_date = models.CharField(db_column='startDate', blank=True, null=True)
    end_date = models.CharField(db_column='endDate', blank=True, null=True)

    class Meta:
        db_table = "tblPrintedReportsHistory"


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
    final_data["total"] = str("{:,.0f}".format(float(grand_total))) + " FC"
    empty_data = []
    empty_data.append({"text2": "\n\n\n\n\n"})
    final_data["data2"] = empty_data
    final_data["data"] = invoice_data
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
    final_data["total"] = str("{:,.0f}".format(float(grand_total))) + " FC"
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
            if family.family_type:
                dictbase["familyType"] = family.family_type.alt_language
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
                    values = {}
                    if str(membre.relationship.relation).lower() in ["spouse", "époux"]:
                        values["numero"] = str(row)
                        values["libelle"] = "Conjoint(e)"
                        values["chfid"] = membre.chf_id
                        values["FirstName"] = membre.last_name
                        values["LastName"] = membre.other_names
                        values["dob"] = str(membre.dob)
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
                        values["dob"] = str(membre.dob)
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
                        values2["dob"] = str(membre.dob)
                        if membre.gender:
                            values2["sex"] = str(membre.gender.code)
                        data2.append(values2)
                row += 1
            insure_policy = InsureePolicy.objects.filter(
                insuree=head.id if head else 0, validity_to__isnull=True
            )
            dictbase["total"] = ""
            dictbase["jour"] = "...."
            dictbase["mois"] = "...."
            dictbase["annee"] = "...."
            if insure_policy:
                inspolicy  = insure_policy[0]
                policy = Policy.objects.filter(id=inspolicy.policy.id).first()
                if policy:
                    dictbase["total"] = str("{:,.0f}".format(float(policy.value))) + " FC " + amount_to_text_fr(int(policy.value), 'FC')
                    dictbase["jour"] = str(policy.start_date).split("-")[2]
                    dictbase["mois"] = str(policy.start_date).split("-")[1]
                    dictbase["annee"] = str(policy.start_date).split("-")[0]
            dictbase["immat"] = " "
            dictbase["firstName"] = " "
            dictbase["lastName"] = " "
            dictbase["address"] = " "
            if head:
                dictbase["immat"] = head.chf_id
                dictbase["firstName"] = head.last_name
                dictbase["lastName"] = head.other_names
                dictbase["address"] = family.address
            if head and head.gender:
                if head.gender.code == 'M':
                    dictbase["civiliteM"] = "x"
                    dictbase["civiliteF"] = ""
                if head.gender.code == 'F':
                    dictbase["civiliteM"] = "x"
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
                dictbase["PhotoInsuree"] = "data:image/png;base64,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"
    # print(dictbase)
    return dictbase