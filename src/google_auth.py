import requests
import yaml

from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from exceptions import InvalidTokenException

with open("secrets.yaml") as f:
    secrets = yaml.load(f, Loader=yaml.FullLoader)
client_id = secrets["Google client ID"]
client_secret = secrets["Google client secret"]


def auth_1():
    response = requests.post("https://oauth2.googleapis.com/device/code", params={
        "client_id": client_id,
        "scope": "email profile", })
    return response.json()


def auth_2(device_code):
    response = requests.post("https://oauth2.googleapis.com/token", params={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": device_code,
        "grant_type": "http://oauth.net/grant_type/device/1.0"
    })
    try:
        return {"access_token": response.json()["id_token"]}
    except:
        return {"error": "Not authorized."}, 403


def token_to_account_id(token):
    try:
        idinfo = id_token.verify_oauth2_token(token, grequests.Request(), client_id)
        return idinfo["sub"]
    except Exception as e:
        print(e)
        raise InvalidTokenException

