import requests
import yaml
from urllib.parse import parse_qsl

from exceptions import InvalidTokenException

with open("secrets.yaml") as f:
    secrets = yaml.load(f, Loader=yaml.FullLoader)

client_id = secrets["Github client ID"]
client_secret = secrets["Github client secret"]


def auth_1():
    response = requests.post("https://github.com/login/device/code", params={
        "client_id": client_id,
        "scope": "user:email", })
    return dict(parse_qsl(response.text))


def auth_2(device_code):
    response = requests.post("https://github.com/login/oauth/access_token", params={
        "client_id": client_id,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
    })
    try:
        return {"access_token": dict(parse_qsl(response.text))["access_token"]}
    except:
        return {"error": "Not authorized."}, 403


def token_to_account_id(token):
    try:
        response = requests.get("https://api.github.com/user", headers={'Authorization': f"token {token}"})
        return response.json()['id']
    except Exception as e:
        print(e)
        raise InvalidTokenException