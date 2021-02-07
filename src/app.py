import traceback

from flask import Flask, request, render_template, make_response
from flask_restplus import Api, Resource, fields
import google_auth
import github_auth

from exceptions import (
    InvalidTokenException,
    InvalidRequestException,
    NotAllowedException,
    UnknownItemException,
    InitialAdminRoleException,
    UserAlreadyExistsException,
    InvalidEmailAddress,
    WrongUsernameOrPassword,
    EmailNotValidated,
    AccountBlocked,
    RoleCantChangeException,
    OneFieldAtATimeException,
    SoldOutException,
    TryingToResellTooManyTicketsException,
    RemoveTicketFirstException
)
from users import UsersContext, Role, AccessType
from events import EventsContext
from tickets import TicketsContext
from currencies import currencies
from phonenumbers.phonenumberutil import NumberParseException


app = Flask(__name__)
app.config['RESTPLUS_VALIDATE'] = True
api = Api()
api.init_app(app)


def catch_exceptions(func):
    try:
        ret_val = func()
    except AccountBlocked:
        return {"error": "Account blocked."}, 401
    except WrongUsernameOrPassword:
        return {"error": "Wrong username or password."}, 401
    except InvalidTokenException:
        return {"error": "Token invalid."}, 401
    except EmailNotValidated:
        return {"error": "Account not verified."}, 401
    except NotAllowedException:
        return {"error": "Not authorized."}, 403
    except UserAlreadyExistsException:
        return {"error": "User already exists."}, 400
    except (InvalidRequestException, InvalidEmailAddress, NumberParseException):
        return {"error": "Invalid request."}, 400
    except UnknownItemException:
        return {"error": "Not found."}, 404
    except InitialAdminRoleException:
        return {"error": "Can't change admin username or role."}, 400
    except RoleCantChangeException:
        return {"error": "Role can't be modified."}, 400
    except OneFieldAtATimeException:
        return {"error": "Only one field can be updated at a time."}, 400
    except SoldOutException:
        return {"error": "Event sold out."}, 400
    except TryingToResellTooManyTicketsException:
        return {"error": "You cannot resell that many tickets."}, 400
    except RemoveTicketFirstException:
        return {"error": "Cannot delete buyer when associated with ticket."}, 400
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}, 500
    return ret_val


@api.route("/register")
class Register(Resource):
    @api.doc(body=api.model('register', {
        'email': fields.String(required=True),
        'password': fields.String(required=True),
        'name': fields.String,
        'role': fields.String(enum=[
            Role.organizer,
            Role.reseller
        ]),
    }))
    def post(self):
        with UsersContext(request) as users:
            return catch_exceptions(users.register)


@api.route("/google-device-auth-step-1")
class GoogleAuth1(Resource):
    def get(self):
        return google_auth.auth_1()


@api.route("/google-device-auth-step-2")
class GoogleAuth2(Resource):
    @api.doc(body=api.model('google-auth-2', {
        'device_code': fields.String
    }))
    def post(self):
        device_code = request.get_json()["device_code"]
        return google_auth.auth_2(device_code)


@api.route("/github-device-auth-step-1")
class GoogleAuth1(Resource):
    def get(self):
        return github_auth.auth_1()


@api.route("/github-device-auth-step-2")
class GoogleAuth2(Resource):
    @api.doc(body=api.model('github-auth-2', {
        'device_code': fields.String
    }))
    def post(self):
        device_code = request.get_json()["device_code"]
        return github_auth.auth_2(device_code)


@api.route("/activate/<code>", doc=False)
class Activate(Resource):
    def get(self, code):
        with UsersContext(request) as users:
            is_activated = users.activate(code)
        if is_activated:
            html = render_template("activate/active.html")
        else:
            html = render_template("activate/invalid.html")
        return make_response(html, 200, {'Content-Type': 'text/html'})


@api.route("/login")
class Login(Resource):
    @api.doc(body=api.model('login', {
        'email': fields.String,
        'password': fields.String,
    }))
    def post(self):
        with UsersContext(request) as users:
            return catch_exceptions(users.login_user)


access_parser = api.parser()
access_parser.add_argument('access-token', location='headers')
access_parser.add_argument('access-type',
                           type=fields.String(enum=[
                               AccessType.email,
                               AccessType.google,
                               AccessType.github]),
                           location='headers')

update_user = api.model('user', {
    'email': fields.String,
    'password': fields.String,
    'role': fields.String,
    'name': fields.String,
    'block': fields.Boolean,
})


@api.route("/myself", methods=["GET"])
@api.expect(access_parser)
class Users(Resource):
    def get(self):
        with UsersContext(request) as users:
            return catch_exceptions(users.read_myself)


@api.route("/users", methods=["GET"])
@api.expect(access_parser)
class Users(Resource):
    def get(self):
        with UsersContext(request) as users:
            return catch_exceptions(users.read)


@api.route("/users/<user_id>", methods=["GET", "PUT", "DELETE"])
@api.expect(access_parser)
class User(Resource):
    def get(self, user_id):
        with UsersContext(request, user_id) as users:
            return catch_exceptions(users.read)

    def delete(self, user_id):
        with UsersContext(request, user_id) as users:
            return catch_exceptions(users.remove)

    @api.doc(body=update_user)
    def put(self, user_id):
        with UsersContext(request, user_id) as users:
            return catch_exceptions(users.update)


buyer = api.model('buyer', {
    'name': fields.String,
    'phone': fields.String,
    'email': fields.String,
})

sell_ticket = api.model('ticket', {
    'event_id': fields.Integer(required=True),
    'seller_id': fields.Integer,
    'buyer': fields.Nested(buyer)
})

@api.route("/sold-tickets", methods=["GET", "POST"])
@api.expect(access_parser)
class Tickets(Resource):
    def get(self):
        with TicketsContext(request) as tickets:
            return catch_exceptions(tickets.read)

    @api.doc(body=sell_ticket)
    def post(self):
        with TicketsContext(request) as tickets:
            return catch_exceptions(tickets.create)


@api.route("/sold-tickets/<ticket_id>", methods=["GET", "DELETE"])
@api.expect(access_parser)
class Ticket(Resource):
    def get(self, ticket_id):
        with TicketsContext(request, ticket_id) as tickets:
            return catch_exceptions(tickets.read)

    def delete(self, ticket_id):
        with TicketsContext(request, ticket_id) as tickets:
            return catch_exceptions(tickets.remove)


reseller = api.model('reseller', {
    'seller_id': fields.Integer,
    'number_of_tickets': fields.Integer
})

create_event = api.model('event', {
    'title': fields.String(required=True),
    'price': fields.String(required=True),
    'currency_code': fields.String(enum=currencies, required=True),
    'time': fields.DateTime(required=True),
    'number_of_tickets': fields.Integer(required=True),
    'organizer_id': fields.Integer,
    'resellers': fields.List(fields.Nested(reseller))
})

update_event = api.model('event', {
    'title': fields.String,
    'price': fields.String,
    'currency_code': fields.String(enum=currencies),
    'time': fields.DateTime,
    'number_of_tickets': fields.Integer,
    'organizer_id': fields.Integer,
    'resellers': fields.List(fields.Nested(reseller))
})


@api.route("/events", methods=["GET", "POST"])
@api.expect(access_parser)
class Users(Resource):
    def get(self):
        with EventsContext(request) as events:
            return catch_exceptions(events.read)

    @api.doc(body=create_event)
    def post(self):
        with EventsContext(request) as events:
            return catch_exceptions(events.create_or_update)


@api.route("/events/<event_id>", methods=["GET", "PUT", "DELETE"])
@api.expect(access_parser)
class Users(Resource):
    def get(self, event_id):
        with EventsContext(request, event_id) as events:
            return catch_exceptions(events.read)

    @api.doc(body=update_event)
    def put(self, event_id):
        with EventsContext(request, event_id) as events:
            return catch_exceptions(events.create_or_update)

    def delete(self, event_id):
        with EventsContext(request, event_id) as events:
            return catch_exceptions(events.remove)


@api.route("/buyers", methods=["GET"])
@api.expect(access_parser)
class Users(Resource):
    def get(self):
        with TicketsContext(request) as tickets:
            return catch_exceptions(tickets.read_buyers)


@api.route("/buyers/<buyer_id>", methods=["GET", "DELETE"])
@api.expect(access_parser)
class Users(Resource):
    def get(self, buyer_id):
        with TicketsContext(request, buyer_id=buyer_id) as tickets:
            return catch_exceptions(tickets.read_buyers)

    def delete(self, buyer_id):
        with TicketsContext(request, buyer_id=buyer_id) as tickets:
            return catch_exceptions(tickets.remove_buyer)


if __name__ == "__main__":
    with UsersContext(None) as users:
        users.create_admin_user()
    app.run(host="0.0.0.0", port=5000, debug=True)
