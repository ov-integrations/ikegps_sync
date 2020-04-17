from IKEIntegration import Integration
import json

with open('settings.json', "rb") as PFile:
    password_data = json.loads(PFile.read().decode('utf-8'))

url_onevizion = password_data["urlOneVizion"]
login_onevizion = password_data["loginOneVizion"]
pass_onevizion = password_data["passOneVizion"]

url_ike = password_data["urlIKE"]
login_ike = password_data["loginIKE"]
pass_ike = password_data["passIKE"]

ike_integration = Integration(url_onevizion, login_onevizion, pass_onevizion, url_ike, login_ike, pass_ike)
ike_integration.start_integration()