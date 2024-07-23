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
        conjointe = ""
        chef_menage = ""
        data["chfid"] = ""
        data["chfid2"] = ""
        chef_menage = insuree_obj.last_name + " " + insuree_obj.other_names
        data["chfid"] = insuree_obj.chf_id
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
                        data["chfid2"] = membre.chf_id
                        mother_ok = True
                    if mother_ok:
                        break
        data["FullFathersName"] = chef_menage
        data["FullMothersName"] = conjointe
        insure_policies = InsureePolicy.objects.filter(
            insuree=insuree_obj.id, policy__status=2).order_by('-id')
        data["DateExpiration"] = ""
        data["dateEmission"] = ""
        if insure_policies:
            insure_policy = insure_policies[0]
            if insure_policy.policy.creation_date:
                policy_date = datetime.datetime.strptime(str(insure_policy.policy.creation_date), "%Y-%m-%d %H:%M:%S.%f")
                policy_date_str = policy_date.strftime("%d/%m/%Y")
                data["dateEmission"] = str(policy_date_str)
                expiry_date = insure_policy.policy.creation_date + core.datetimedelta(years=5)
                new_expiry_date = datetime.datetime.strptime(str(expiry_date), "%Y-%m-%d %H:%M:%S.%f")
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