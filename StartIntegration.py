import IKEIntegration
import json

with open('settings.json', "rb") as PFile:
    password_data = json.loads(PFile.read().decode('utf-8'))

url_onevizion = password_data["urlOneVizion"]
login_onevizion = password_data["loginOneVizion"]
pass_onevizion = password_data["passOneVizion"]

url_ike = password_data["urlIKE"]
login_ike = password_data["loginIKE"]
pass_ike = password_data["passIKE"]

with open('ihub_process_id', "rb") as PFile:
    process_id = PFile.read().decode('utf-8')

IKEIntegration.Integration(process_id=process_id, url_onevizion=url_onevizion, login_onevizion=login_onevizion, pass_onevizion=pass_onevizion, url_ike=url_ike, login_ike=login_ike, pass_ike=pass_ike)
