from database import SoldTicket, Event, Buyer
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
    RemoveTicketFirstException
)
from users import Users, Role
from events import EventsContext, Events
import phonenumbers
from validate_email import validate_email



class TicketsContext:
    def __init__(self, request, ticket_id=None, buyer_id=None):
        self._request = request
        self.ticket_id = ticket_id
        self.buyer_id = buyer_id

    def __enter__(self):
        self.eContext = EventsContext(self._request)
        events = self.eContext.__enter__()
        users = events.users
        return Tickets(events.db_session, users, events, self._request, self.ticket_id, self.buyer_id)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.eContext.__exit__(exc_type, exc_value, exc_traceback)


class Tickets:

    def __init__(self, db_session, users: Users, events: Events, request, ticket_id, buyer_id):
        self.storage = _Storage(db_session)
        self.buyer = _Buyer(db_session)
        self.users = users
        self.events = events
        self.request = request
        self.ticket_id = ticket_id
        self.buyer_id = buyer_id

    def read_buyers(self):
        self.users.set_logged_in()
        if self.users.logged_in_user.role != Role.admin:
            raise NotAllowedException
        if self.buyer_id:
            try:
                e_dict = vars(self.buyer.get(self.buyer_id))
            except:
                raise UnknownItemException

            e_dict.pop("_sa_instance_state")
            return {"buyer": e_dict}
        else:
            ret_val = {"buyers": []}
            for entry in self.buyer.get_all():
                e_dict = vars(entry)
                e_dict.pop("_sa_instance_state")
                ret_val["buyers"].append(e_dict)
            return ret_val

    def remove_buyer(self):
        self.users.set_logged_in()
        if self.users.logged_in_user.role != Role.admin:
            raise NotAllowedException
        ret = self.read_buyers()
        try:
            self.buyer.remove(self.buyer_id)
        except:
            raise RemoveTicketFirstException
        return {**ret, "message": "Buyer removed."}


    def read(self):
        if self.ticket_id:
            try:
                e_dict = vars(self.storage.get(self.ticket_id))
            except:
                raise UnknownItemException
            e_dict.pop("_sa_instance_state")
            return {"ticket": e_dict}
        else:
            ret_val = {"tickets": []}
            for entry in self.storage.get_all():
                e_dict = vars(entry)
                e_dict.pop("_sa_instance_state")
                ret_val["tickets"].append(e_dict)
            return ret_val

    def create(self):
        body = self.request.get_json()
        event_id = body["event_id"]
        event_orm = self.events.storage.get(event_id)
        if not event_orm:
            raise InvalidRequestException

        if "seller_id" in body:
            seller_id = body["seller_id"]
            if not self.users.storage.get(seller_id):
                raise InvalidRequestException
        else:
            try:
                self.users.set_logged_in()
            except Exception as e:
                print(e)
                raise InvalidRequestException
            seller_id = self.users.logged_in_user.user_id

        user_orm = self.users.storage.get(seller_id)
        if user_orm.role == Role.organizer:
            count = self.storage.ticket_count_for_seller(seller_id=seller_id)
            resold_events = self.events.resoldEvent.get_by_event(event_id)
            reseller_count = 0
            for resold_event in resold_events:
                reseller_count += resold_event.number_of_tickets
            if event_orm.number_of_tickets - reseller_count <= count:
                raise SoldOutException
        elif user_orm.role == Role.reseller:
            resold_event = self.events.resoldEvent.get(event_id, seller_id)
            count = self.storage.ticket_count_for_seller(seller_id=seller_id)
            if resold_event.number_of_tickets <= count:
                raise SoldOutException
        else:
            raise NotAllowedException
        buyer_dict = body["buyer"]
        if not phonenumbers.is_valid_number(phonenumbers.parse(buyer_dict["phone"], None)):
            raise InvalidRequestException
        valid = validate_email(email_address=buyer_dict["email"], check_mx=False)
        if not valid:
            raise InvalidEmailAddress
        buyer_obj = Buyer(
            name=buyer_dict["name"],
            phone=buyer_dict["phone"],
            email=buyer_dict["email"]
        )
        self.buyer.create(buyer_obj)

        ticket_obj = SoldTicket(
            event_id=event_id,
            seller_id=seller_id,
            buyer_id=buyer_obj.id
        )
        self.storage.create(ticket_obj)
        self.ticket_id = ticket_obj.id
        return self.read()

    def remove(self):
        self.users.set_logged_in()
        if self.users.logged_in_user.role != Role.admin:
            raise NotAllowedException
        ret = self.read()
        self.storage.remove(self.ticket_id)
        return {**ret, "message": "Ticket removed."}


class _Storage:
    def __init__(self, db_session):
        self._db_session = db_session

    def remove(self, ticket_id):
        self._db_session.delete(self.get(ticket_id))
        self._db_session.commit()

    def create(self, ticket_obj):
        self._db_session.add(ticket_obj)
        self._db_session.commit()

    def ticket_count_for_seller(self, seller_id):
        return self._db_session.query(SoldTicket).filter_by(seller_id=seller_id).count()

    def get(self, ticket_id) -> SoldTicket:
        return self._db_session.query(SoldTicket).filter_by(id=ticket_id).first()

    def get_all(self):
        return self._db_session.query(SoldTicket)

    def update_field(self, ticket_id, field, value):
        ticket = self._db_session.query(SoldTicket).filter_by(id=ticket_id).first()
        setattr(ticket, field, value)
        self._db_session.commit()

    def commit_changes(self):
        self._db_session.commit()


class _Buyer:
    def __init__(self, db_session):
        self._db_session = db_session

    def remove(self, buyer_id):
        self._db_session.delete(self.get(buyer_id))
        self._db_session.commit()

    def create(self, buyer_obj):
        self._db_session.add(buyer_obj)
        self._db_session.commit()

    def buyer_count_for_seller(self, seller_id):
        return self._db_session.query(Buyer).filter_by(seller_id=seller_id).count()

    def get(self, buyer_id) -> Buyer:
        return self._db_session.query(Buyer).filter_by(id=buyer_id).first()

    def get_all(self):
        return self._db_session.query(Buyer)

    def update_field(self, buyer_id, field, value):
        buyer = self._db_session.query(Buyer).filter_by(id=buyer_id).first()
        setattr(buyer, field, value)
        self._db_session.commit()

    def commit_changes(self):
        self._db_session.commit()
