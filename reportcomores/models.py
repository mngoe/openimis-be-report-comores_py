from django.db import models
from report.services import run_stored_proc_report
from insuree.models import Insuree, Family
import qrcode
from io import BytesIO
import base64, core, datetime
from insuree.models import InsureePolicy

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
        nom_conjointe = ""
        prenom_conjointe = ""
        nom_chef_menage = ""
        prenom_chef_menage = ""
        chfid2 = ""
        nom_chef_menage = insuree_obj.last_name
        prenom_chef_menage = insuree_obj.other_names
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
                        nom_conjointe = membre.last_name
                        prenom_conjointe = membre.other_names
                        chfid2 = membre.chf_id
                        mother_ok = True
                    if mother_ok:
                        break
        # chef_menage = chef_menage[:19] #19 Caracteres max
        # conjointe = conjointe[:19] #19 Caracteres max
        data["FathersFirstName"] = nom_chef_menage
        data["FathersLastName"] = prenom_chef_menage
        data["MothersFirstName"] = nom_conjointe
        data["MothersLastName"] = prenom_conjointe
        data["chfid"] = chfid
        data["chfid2"] = chfid2
        if insuree_obj.family:
            if insuree_obj.family.parent:
                # We exchange the head and the spouse
                data["FathersFirstName"] = nom_conjointe
                data["FathersLastName"] = prenom_conjointe
                data["MothersFirstName"] = nom_chef_menage
                data["MothersLastName"] = prenom_chef_menage
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