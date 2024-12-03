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
    final_data["moisReleve"] = my_dict.get(today_date.split("-")[1])
    # Get the district
    if hflocation and hflocation!="0" :
        hflocationObj = HealthFacility.objects.filter(
            code=hflocation,
            legal_form__code='P',
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
    final_data["moisReleve"] = my_dict.get(today_date.split("-")[1])
    # Get the district
    if hflocation and hflocation!="0" :
        hflocationObj = HealthFacility.objects.filter(
            code=hflocation,
            validity_to__isnull=True
        ).exclude(legal_form__code='P').first()
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