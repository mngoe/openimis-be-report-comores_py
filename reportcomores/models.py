from django.db import models
from report.services import run_stored_proc_report
from insuree.models import Insuree, Family
import qrcode
from io import BytesIO
import base64, time, datetime
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
        maintenant = str(time.strftime("%d/%m/%Y"))
        data["dateEmission"] = maintenant
        mothers_name = ""
        fathers_name = ""
        data["chfid"] = ""
        data["chfid2"] = ""
        insuree_rel = ""
        if insuree_obj.relationship:
            insuree_rel = str(insuree_obj.relationship.relation).lower()
        if insuree_rel not in ["father", "mother"]:
            if insuree_obj.family:
                members = Insuree.objects.filter(
                    family_id=insuree_obj.family.id
                ).exclude(id=insuree_obj.id)
                father_ok = False
                mother_ok = False
                for membre in members:
                    if membre.relationship:
                        if str(membre.relationship.relation).lower() == "father":
                            fathers_name = membre.last_name + " " + membre.other_names
                            data["chfid"] = membre.chf_id
                            father_ok = True
                        if str(membre.relationship.relation).lower() == "mother":
                            mothers_name = membre.last_name + " " + membre.other_names
                            data["chfid2"] = membre.chf_id
                            mother_ok = True
                        if mother_ok and father_ok:
                            break
        data["FullFathersName"] = fathers_name
        data["FullMothersName"] = mothers_name
        insure_policy = InsureePolicy.objects.filter(
            insuree=insuree_obj.id, policy__status=2).order_by('-id')
        data["DateExpiration"] = ""
        if insure_policy:
            policy = insure_policy[0]
            if policy.expiry_date:
                format = "%Y-%m-%d"
                expiry_date = datetime.datetime.strptime(str(policy.expiry_date), format)
                date_str = expiry_date.strftime("%d/%m/%Y")
                data["DateExpiration"] = str(date_str)
        # Create qr code instance
        qr = qrcode.QRCode()
        # The data that you want to store
        # Add data
        qr.add_data(data)

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