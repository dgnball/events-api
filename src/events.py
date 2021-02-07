from database import Event, ResoldEvent
from decimal import Decimal
from exceptions import InvalidRequestException, NotAllowedException, TryingToResellTooManyTicketsException, \
    UnknownItemException
from users import UsersContext, Users, Role
import iso8601
import datetime
import pytz

class EventsContext:
    def __init__(self, request, event_id=None):
        self._request = request
        self.event_id = event_id

    def __enter__(self):
        self.uContext = UsersContext(self._request)
        users = self.uContext.__enter__()
        return Events(self.uContext.db_session, users, self._request, self.event_id)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.uContext.__exit__(exc_type, exc_value, exc_traceback)


class Events:

    def __init__(self, db_session, users: Users, request, event_id):
        self.storage = _Storage(db_session)
        self.resoldEvent = _ResoldEvent(db_session)
        self.db_session = db_session
        self.users = users
        self.request = request
        self.event_id = event_id

    def database_to_json(self, event):
        event.pop("_sa_instance_state")
        event["price"] = str(event.pop("cent_price") / 100)
        event["time"] = event.pop("time").isoformat()

        resold_events = self.resoldEvent.get_by_event(event["id"])
        if resold_events:
            event["resellers"] = []
        for resold in resold_events:
            r_dict = vars(resold)
            r_dict.pop("_sa_instance_state")
            r_dict.pop("event_id")
            event["resellers"].append(r_dict)

    def read(self):
        if self.event_id:
            try:
                e_dict = vars(self.storage.get(self.event_id))
            except:
                raise UnknownItemException
            self.database_to_json(e_dict)
            return {"event": e_dict}
        else:
            ret_val = {"events": []}
            for entry in self.storage.get_all():
                e_dict = vars(entry)
                self.database_to_json(e_dict)
                ret_val["events"].append(e_dict)
            return ret_val

    def create_or_update(self):
        self.users.set_logged_in()
        if self.users.logged_in_user.role not in [Role.admin, Role.organizer]:
            raise NotAllowedException
        body = self.request.json
        cent_price = None
        if "price" in body:
            try:
                raw_price_value = body["price"]
                cent_price = int(Decimal(raw_price_value) * 100)
            except Exception as e:
                print(e)
                raise InvalidRequestException

        date_object = None
        if "time" in body:
            try:
                date_object = iso8601.parse_date(body["time"])
            except Exception as e:
                print(e)
                raise InvalidRequestException
            if date_object < datetime.datetime.now().replace(tzinfo=pytz.UTC):
                raise InvalidRequestException

        organizer_id = None
        if "organizer_id" in body:
            organizer_id = self.request.json["organizer_id"]
            if not self.users.storage.get(organizer_id):
                raise InvalidRequestException
        elif not self.event_id:
            organizer_id = self.users.logged_in_user.user_id

        if "number_of_tickets" in body:
            try:
                x = int(body["number_of_tickets"])
                if x <= 0:
                    raise InvalidRequestException
            except:
                raise InvalidRequestException

        if self.event_id:
            event_obj = self.storage.get(self.event_id)
            if cent_price:
                event_obj.cent_price = cent_price
            if date_object:
                event_obj.time = date_object
            if organizer_id:
                event_obj.organizer_id = organizer_id
            if "title" in body:
                event_obj.title = body["title"]
            if "currency_code" in body:
                event_obj.currency_code = body["currency_code"]
            if "number_of_tickets" in body:
                event_obj.number_of_tickets = body["number_of_tickets"]
            self.storage.commit_changes()
        else:
            event_obj = Event(
                title=body["title"],
                cent_price=cent_price,
                currency_code=body["currency_code"],
                time=date_object,
                number_of_tickets=body["number_of_tickets"],
                organizer_id=organizer_id
            )
            self.storage.create(event_obj)

        if "resellers" in body:
            self.create_update_reseller(body["resellers"], event_obj)

        self.event_id = event_obj.id
        return self.read()

    def create_update_reseller(self, resellers, event_obj):
        total_tickets_to_resell = 0
        for reseller in resellers:
            total_tickets_to_resell += reseller["number_of_tickets"]
        if total_tickets_to_resell > event_obj.number_of_tickets:
            raise TryingToResellTooManyTicketsException

        for reseller in resellers:
            if "number_of_tickets" in reseller:
                try:
                    x = int(reseller["number_of_tickets"])
                    if x <= 0:
                        raise InvalidRequestException
                except:
                    raise InvalidRequestException


            r_event_obj = ResoldEvent(
                seller_id=reseller["seller_id"],
                number_of_tickets=reseller["number_of_tickets"],
                event_id=event_obj.id
            )
            self.resoldEvent.create(r_event_obj)

    def remove(self):
        self.users.set_logged_in()
        if self.users.logged_in_user.role not in [Role.admin, Role.organizer]:
            raise NotAllowedException
        ret = self.read()
        self.storage.remove(self.event_id)
        return {**ret, "message": "Event removed."}



class _Storage:
    def __init__(self, db_session):
        self._db_session = db_session

    def remove(self, event_id):
        self._db_session.delete(self.get(event_id))
        self._db_session.commit()

    def create(self, event_obj):
        self._db_session.add(event_obj)
        self._db_session.commit()

    def get(self, event_id) -> Event:
        return self._db_session.query(Event).filter_by(id=event_id).first()

    def get_all(self):
        return self._db_session.query(Event)

    def update_field(self, event_id, field, value):
        event = self._db_session.query(Event).filter_by(id=event_id).first()
        setattr(event, field, value)
        self._db_session.commit()

    def commit_changes(self):
        self._db_session.commit()
        
class _ResoldEvent:
    def __init__(self, db_session):
        self._db_session = db_session

    def remove(self, event_id):
        self._db_session.delete(self.get(event_id))
        self._db_session.commit()

    def create(self, event_obj):
        self._db_session.add(event_obj)
        self._db_session.commit()

    def get_by_event(self, event_id):
        return self._db_session.query(ResoldEvent).filter_by(event_id=event_id)

    def get(self, event_id, seller_id) -> ResoldEvent:
        return self._db_session.query(ResoldEvent).filter_by(
            event_id=event_id, seller_id=seller_id).first()

    def get_all(self):
        return self._db_session.query(ResoldEvent)

    def update_field(self, event_id, field, value):
        event = self._db_session.query(ResoldEvent).filter_by(id=event_id).first()
        setattr(event, field, value)
        self._db_session.commit()

    def commit_changes(self):
        self._db_session.commit()


