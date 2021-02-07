from flask_testing import TestCase
import app
import emails
import google_auth
from users import Role
import os
from unittest.mock import MagicMock
import database


class TestTicketManagerApi(TestCase):
    def test_get_own_user(self):
        body, code = self.get(f"/myself", TestUsers.admin)
        self.assertEqual(200, code)
        self.assertEqual(without(TestUsers.admin, "password"), body)

        body, code = self.get(f"/myself", TestUsers.org_1)
        self.assertEqual(200, code)
        self.assertEqual(without(TestUsers.org_1, "password"), body)

        body, code = self.get(f"/myself", TestUsers.res_1)
        self.assertEqual(200, code)
        self.assertEqual(without(TestUsers.res_1, "password"), body)

    def test_sell_ticket(self):
        event = self.create_event()
        self.sell_ticket(event["id"], TestUsers.org_1["id"])

    def test_sell_out(self):
        event = self.create_event()
        number_of_tickets = event["number_of_tickets"]
        for i in range(number_of_tickets + 1):
            if i == number_of_tickets:
                self.sell_ticket(event["id"], TestUsers.org_1["id"], expect_failure="Event sold out.")
            else:
                self.sell_ticket(event["id"], TestUsers.org_1["id"])

    def test_reseller_sell_ticket(self):
        event = self.create_event()
        reseller_tickets = 5
        self.add_reseller(event["id"], reseller_tickets)
        number_of_tickets = event["number_of_tickets"]
        tickets_organiser_can_sell = number_of_tickets - reseller_tickets
        for i in range(tickets_organiser_can_sell + 1):
            if i == tickets_organiser_can_sell:
                self.sell_ticket(event["id"], TestUsers.org_1["id"], expect_failure="Event sold out.")
            else:
                self.sell_ticket(event["id"], TestUsers.org_1["id"])
        for i in range(reseller_tickets + 1):
            if i == reseller_tickets:
                self.sell_ticket(event["id"], TestUsers.res_1["id"], expect_failure="Event sold out.")
            else:
                self.sell_ticket(event["id"], TestUsers.res_1["id"])

    def test_block_user(self):
        for i in range(4):
            response = self.client.post("/login", json={
                "email": TestUsers.org_1["email"],
                "password": "wrong_password"
            })
            if i == 3:
                self.assertEqual(response.json["error"], "Account blocked.")
            else:
                self.assertEqual(response.json["error"], "Wrong username or password.")
        response = self.client.post("/login", json={
            "email": TestUsers.org_1["email"],
            "password": TestUsers.org_1["password"]
        })
        self.assertEqual(response.json["error"], "Account blocked.")
        body, code = self.put(f"/users/{TestUsers.org_1['id']}", TestUsers.res_1, {"block": False})
        self.assertEqual(403, code)
        body, code = self.put(f"/users/{TestUsers.org_1['id']}", TestUsers.admin, {"block": False})
        self.assertEqual(200, code)
        response = self.client.post("/login", json={
            "email": TestUsers.org_1["email"],
            "password": TestUsers.org_1["password"]
        })
        self.assertTrue("auth_token" in response.json)

    def test_update_event(self):
        """Check a venue organizer can change the event title, time and price.
        Check that they can't give away more tickets to resellers than are available.
        Check that only the venue organizer and admin can modify and delete the event
        """
        event = self.create_event()
        event_changes = {
            "title": "New music concert",
            "price": "63.72",
            "currency_code": "GBP",
            "time": "2021-03-29T00:00:00",
            "number_of_tickets": 20
        }
        self.update_event(event_changes, event["id"])
        event_changes = {
            "resellers": [
                {
                    "seller_id": TestUsers.res_1["id"],
                    "number_of_tickets": 30
                }
            ]
        }
        self.update_event(event_changes, event["id"], expect_failure="You cannot resell that many tickets.")
        event_changes = {
            "title": "My concert"
        }
        self.update_event(event_changes, event["id"], expect_failure="Not authorized.",
                          user=TestUsers.res_1)
        body, code = self.delete("/events/1", user=TestUsers.org_1)
        self.assertEqual(200, code)
        body, code = self.get("/events/1", user=TestUsers.org_1)
        self.assertEqual(404, code)

    def test_buyer_info(self):
        event = self.create_event()
        self.sell_ticket(event["id"], TestUsers.org_1["id"])
        body, code = self.get("/buyers", TestUsers.admin)
        self.assertEqual(200, code)
        self.assertEqual({"buyers": [{
            "id": 1,
            "name": "Joe Blogs",
            "phone": "+441234567890",
            "email": "joe@email.com"
        }]}, body)
        body, code = self.get("/buyers/1", TestUsers.admin)
        self.assertEqual(200, code)
        self.assertEqual({"buyer": {
            "id": 1,
            "name": "Joe Blogs",
            "phone": "+441234567890",
            "email": "joe@email.com"
        }}, body)
        body, code = self.delete("/sold-tickets/1", TestUsers.admin)
        self.assertEqual(200, code)
        body, code = self.delete("/buyers/1", TestUsers.admin)
        self.assertEqual(200, code)
        body, code = self.get("/buyers", TestUsers.admin)
        self.assertEqual(200, code)
        self.assertEqual({"buyers": []}, body)

    def add_reseller(self, event_id, number_of_tickets):

        event = {
            "resellers": [
                {
                    "seller_id": TestUsers.res_1["id"],
                    "number_of_tickets": number_of_tickets
                }
            ]
        }
        body, code = self.put(f"/events/{event_id}", TestUsers.org_1, event)
        self.assertEqual(200, code)
        return body["event"]

    def create_event(self):
        event = {
            "title": "Music concert",
            "price": "60.70",
            "currency_code": "GBP",
            "time": "2021-09-29T10:30:06.937Z",
            "number_of_tickets": 10,
            "organizer_id": TestUsers.org_1["id"],
        }
        body, code = self.post(f"/events", TestUsers.org_1, event)
        self.assertEqual(200, code)
        return body["event"]

    def update_event(self, updates, event_id, expect_failure=None, user=None):
        user = TestUsers.org_1 if user is None else user
        body, code = self.put(f"/events/{event_id}", user, updates)
        if expect_failure:
            self.assertEqual(expect_failure, body["error"])
            return
        self.assertEqual(200, code)
        for key, value in updates.items():
            self.assertEqual(body["event"][key], value)

    def sell_ticket(self, event_id, seller_id, expect_failure=None):
        ticket = {
            "event_id": event_id,
            "seller_id": seller_id,
            "buyer": {
                "name": "Joe Blogs",
                "phone": "+441234567890",
                "email": "joe@email.com"
            }
        }
        body, code = self.post(f"/sold-tickets", TestUsers.org_1, ticket)
        if expect_failure:
            self.assertEqual(400, code)
            self.assertEqual({"error": expect_failure}, body)
        else:
            self.assertEqual(200, code)

    def setUp(self) -> None:
        database.recreate_db()
        os.environ["INIT_ADMIN_EMAIL"] = TestUsers.admin["email"]
        os.environ["ADMIN_PASSWORD"] = TestUsers.admin["password"]
        os.environ["SECRET_KEY"] = "SECRET_KEY"
        os.environ["SECURITY_PASSWORD_SALT"] = "SECURITY_PASSWORD_SALT"
        os.environ["APP_URL"] = "http://localhost:5000"
        os.environ["SMTP_SERVER"] = "localhost"
        os.environ["SMTP_PORT"] = "1025"
        with app.UsersContext(None) as users:
            users.create_admin_user()
        smtp_mock = MagicMock()
        emails.smtplib.SMTP = smtp_mock
        google_auth.id_token.verify_oauth2_token = MagicMock(return_value={"sub": "123"})
        body, code = self.post("/register", data=TestUsers.org_1)
        self.assertEqual(200, code, body.get("error", ""))
        activate_url = ""
        for call in smtp_mock.mock_calls:
            if "sendmail" in call[0]:
                activate_url = call[1][2].split("http://localhost:5000")[1].rstrip()
        print(activate_url)
        body, code = self.get(activate_url)
        self.assertEqual(200, code)
        body, code = self.get(f"/myself", TestUsers.res_1)
        self.assertEqual(200, code)
        body, code = self.put(f"/users/{body['id']}", TestUsers.res_1, {'role': Role.reseller})
        self.assertEqual(200, code)
        body, code = self.put(f"/users/{body['id']}", TestUsers.res_1, {'name': TestUsers.res_1["name"]})
        self.assertEqual(200, code)

    def login(self, user):
        if "email" in user and user['email']:
            response = self.client.post("/login", json={
                "email": user["email"],
                "password": user["password"]
            })
            token = response.json["auth_token"]
            method = "email"
        else:
            token = "i am a google token"
            method = "google"
        return token, method

    def get(self, url, user=None):
        """Login if no auth tokens, then run get."""
        if user:
            token, access_type = self.login(user)
            response = self.client.get(url, headers={
                "access-token": token,
                "access-type": access_type
            })
        else:
            response = self.client.get(url)
        return response.json, response.status_code

    def delete(self, url, user):
        """Login if no auth tokens, then run delete."""
        token, access_type = self.login(user)
        response = self.client.delete(url, headers={
            "access-token": token,
            "access-type": access_type
        })
        return response.json, response.status_code

    def post(self, url, user=None, data=None):
        """Login if no auth tokens, then run post."""
        if user:
            token, access_type = self.login(user)
            response = self.client.post(url, headers={
                "access-token": token,
                "access-type": access_type
            }, json=data)
        else:
            response = self.client.post(url, json=data)
        self.assertIsNotNone(response.json, response.status_code)
        return response.json, response.status_code

    def put(self, url, user, data):
        """Login if no auth tokens, then run post."""
        token, access_type = self.login(user)
        response = self.client.put(url, headers={
            "access-token": token,
            "access-type": access_type
        }, json=data)
        return response.json, response.status_code

    def create_app(self):
        return app.app


def without(d, key):
    new_d = d.copy()
    new_d.pop(key)
    return new_d


class TestUsers:
    admin = {
        "id": 1,
        "name": "default admin", "role": Role.admin,
        "email": "admin@localmail.com", "password": "password1",
        "foreign_user_id": None
    }
    org_1 = {
        "id": 2,
        "name": "org1", "role": Role.organizer,
        "email": "org1@localmail.com", "password": "password2",
        "foreign_user_id": None
    }
    res_1 = {
        "id": 3,
        "name": "res1", "role": Role.reseller,
        "email": None, "password": None,
        "foreign_user_id": "123"
    }
