from exceptions import (
    NotAllowedException,
    UnknownItemException,
    InitialAdminRoleException,
    UserAlreadyExistsException,
    InvalidTokenException,
    InvalidEmailAddress,
    InvalidRequestException,
    WrongUsernameOrPassword,
    EmailNotValidated,
    AccountBlocked
)
import datetime
import jwt

from database import User, DBSession
import os
import jwt
import google_auth
import github_auth
import emails
from werkzeug.security import generate_password_hash, check_password_hash
from exceptions import InvalidRequestException, RoleCantChangeException, OneFieldAtATimeException


class Role:
    admin = "admin"
    organizer = "organizer"
    reseller = "reseller"


class AccessType:
    email = "email"
    google = "google"
    github = "github"


class UsersContext:
    def __init__(self, request, user_id=None):
        self._request = request
        self._user_id = user_id

    def __enter__(self):
        self.db_session = DBSession()
        return Users(self.db_session, self._request, self._user_id)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.db_session.close()


class LoggedInUser:

    def __init__(self, user_id, role, owned_events = None):
        self.user_id = int(user_id) if user_id else None
        self.role = role
        self.owned_events = owned_events


class Users:

    def __init__(self, db_session, request, user_id):
        self.storage = _Storage(db_session)
        self.logged_in_user = LoggedInUser(None, None)
        self.user_id = int(user_id) if user_id else None
        self.request = request

    def create_admin_user(self):
        hashed_password = generate_password_hash(os.environ["ADMIN_PASSWORD"])
        if self.storage.empty():
            user = User(
                email=os.environ["INIT_ADMIN_EMAIL"],
                hashed_password=hashed_password,
                role=Role.admin,
                account_verified=True,
                login_fail_count=0,
                name="default admin"
            )
            self.storage.create(user)

    def login_user(self):
        """Used only for email logins."""
        body = self.request.get_json()
        user_orm = self.storage.get_user_by_email(body["email"])
        if not user_orm:
            raise WrongUsernameOrPassword
        if user_orm.login_fail_count >= 3:
            raise AccountBlocked
        if not check_password_hash(user_orm.hashed_password, body["password"]):
            user_orm.login_fail_count += 1
            self.storage.commit_changes()
            raise WrongUsernameOrPassword
        if not user_orm.account_verified:
            raise EmailNotValidated
        if user_orm.login_fail_count > 0:
            user_orm.login_fail_count = 0
            self.storage.commit_changes()
        payload = {
            "user_id": user_orm.id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=30),
        }
        token = jwt.encode(payload, os.environ["SECRET_KEY"])
        return {"auth_token": token.decode()}

    def update(self):
        self._modify_read_user_check()
        body = self.request.get_json()
        if len(body) != 1:
            raise OneFieldAtATimeException
        if "password" in body:
            password_hash = generate_password_hash(body["password"])
            self.update_password(password_hash)
            return {"message": "Password updated."}
        elif "role" in body:
            self.update_role(self.user_id, body["role"])
            ret = self.read()
            return {**ret, "message": "Role updated."}
        elif "block" in body:
            self.update_block(self.user_id, body["block"])
            ret = self.read()
            if body["block"]:
                return {**ret, "message": "User blocked."}
            else:
                return {**ret, "message": "User unblocked."}
        elif "name" in body:
            self.storage.update_field(self.user_id, "name", body["name"])
            ret = self.read()
            return {**ret, "message": "Name updated."}
        else:
            raise InvalidRequestException

    def register(self):
        """
        For email registrations we must first get the email address verified.
        """
        email = self.request.json["email"]
        password = self.request.json["password"]
        if self.storage.email_exists(email):
            raise UserAlreadyExistsException
        emails.register(email)
        hashed_password = generate_password_hash(password)
        user = User(
            email=email,
            hashed_password=hashed_password,
            role=self.request.json["role"] if "role" in self.request.json else None,
            account_verified=False,
            login_fail_count=0,
            name=self.request.json["name"] if "name" in self.request.json else None
        )
        self.storage.create(user)
        return {"message": f"Validation email sent to {email}"}

    def activate(self, code):
        email = emails.activate(code)
        if not email:
            return False
        if self.storage.email_exists(email):
            self.storage.mark_verified(email)
            return True
        return False

    def non_session_read(self, username):
        return self.storage.get(username)

    def _handle_foreign_account(self, account_id):
        """Will look up the foreign account id in the user table. If it doesn't exist,
        a user is created. The new user or existing user is set to be the current user."""
        user = self.storage.get_user_by_foreign_account_id(account_id)
        self.logged_in_user = LoggedInUser(user.id, user.role)

    def set_logged_in(self):
        access_type = self.request.headers["access-type"]
        token = self.request.headers["access-token"]
        if access_type == AccessType.email:
            try:
                data = jwt.decode(token, os.environ["SECRET_KEY"])
                user_id = data["user_id"]
            except Exception as e:
                print(e)
                raise InvalidTokenException
            user = self.storage.get(user_id)
            self.logged_in_user = LoggedInUser(user_id, user.role)
        elif access_type == AccessType.google:
            google_account_id = google_auth.token_to_account_id(token)
            self._handle_foreign_account(google_account_id)
        elif access_type == AccessType.github:
            github_account_id = github_auth.token_to_account_id(token)
            self._handle_foreign_account(github_account_id)
        else:
            raise InvalidTokenException

    def read(self):
        self._modify_read_user_check()
        if self.user_id:
            try:
                user_dict = vars(self.storage.get(self.user_id))
            except:
                raise UnknownItemException
            user_dict.pop("_sa_instance_state")
            user_dict.pop("hashed_password")
        else:
            user_dict = {"users":[]}
            for user in self.storage.get_all():
                entry = vars(user)
                entry.pop("_sa_instance_state")
                entry.pop("hashed_password")
                user_dict["users"].append(entry)
        return user_dict

    def read_myself(self):
        self.set_logged_in()
        user_dict = vars(self.storage.get(self.logged_in_user.user_id))
        user_dict.pop("_sa_instance_state")
        user_dict.pop("hashed_password")
        user_dict.pop("account_verified")
        user_dict.pop("login_fail_count")
        return user_dict

    def remove(self):
        self._modify_read_user_check()
        user_dict = vars(self.storage.get(self.user_id))
        user_dict.pop("_sa_instance_state")
        user_dict.pop("hashed_password")
        self.storage.remove(self.user_id)
        return {"message": "User successfully deleted.", "user": user_dict}

    def update_password(self, hashed_password):
        self._modify_read_user_check()
        self.storage.update_field(self.user_id, "hashed_password", hashed_password)

    def update_role(self, user_id_change, new_role):
        if new_role not in [Role.admin, Role.reseller, Role.organizer]:
            raise InvalidRequestException
        if self.logged_in_user.role != Role.admin and new_role == Role.admin:
            raise NotAllowedException
        user_orm = self.storage.get(user_id_change)
        if user_orm.role != None:
            raise RoleCantChangeException
        self.storage.update_field(self.user_id, "role", new_role)

    def update_block(self, user_id_change, block):
        if self.logged_in_user.role != Role.admin:
            raise NotAllowedException
        user_orm = self.storage.get(user_id_change)
        if block:
            user_orm.login_fail_count = 3
        else:
            user_orm.login_fail_count = 0
        self.storage.commit_changes()

    def _modify_read_user_check(self):
        self.set_logged_in()
        if not self.user_id:  # Means we are about to perform a global operation on the user table
            if self.logged_in_user.role != Role.admin:
                raise NotAllowedException
            else:
                return
        user_to_access = self.storage.get(self.user_id)
        if not user_to_access:
            raise UnknownItemException
        if self.logged_in_user.user_id != self.user_id:
            if self.logged_in_user.role != Role.admin:
                raise NotAllowedException


class _Storage:
    def __init__(self, db_session):
        self._db_session = db_session

    def remove(self, user_id):
        self._db_session.delete(self.get(user_id))
        self._db_session.commit()

    def create(self, user_obj):
        self._db_session.add(user_obj)
        self._db_session.commit()

    def get(self, user_id):
        return self._db_session.query(User).filter_by(id=user_id).first()

    def get_all(self):
        return self._db_session.query(User)

    def update_field(self, user_id, field, value):
        user = self._db_session.query(User).filter_by(id=user_id).first()
        setattr(user, field, value)
        self._db_session.commit()
        return user

    def commit_changes(self):
        self._db_session.commit()

    def empty(self):
        """Returns true if no users."""
        if self._db_session.query(User).count() == 0:
            return True
        return False

    def email_exists(self, email):
        """Returns true if email address is in the database."""
        if self._db_session.query(User).filter_by(email=email).count() != 0:
            return True
        return False

    def admin_users(self, email):
        """Returns true if email address is in the database."""
        if self._db_session.query(User).filter_by(role=Role.admin).count() != 0:
            return True
        return False

    def mark_verified(self, email):
        user = self._db_session.query(User).filter_by(email=email).first()
        setattr(user, "account_verified", True)
        self._db_session.commit()

    def get_user_by_email(self, email) -> User:
        user = self._db_session.query(User).filter_by(email=email).first()
        return user

    def get_user_by_foreign_account_id(self, foreign_user_id) -> User:
        if self._db_session.query(User).filter_by(foreign_user_id=foreign_user_id).count() == 0:
            user = User(foreign_user_id=foreign_user_id)
            self.create(user)
        user = self._db_session.query(User).filter_by(foreign_user_id=foreign_user_id).first()
        return user

    def get_user_by_foreign_user_id(self, email) -> User:
        user = self._db_session.query(User).filter_by(email=email).first()
        return user

