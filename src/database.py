from sqlalchemy import Column, ForeignKey, String, DECIMAL, TIMESTAMP, Integer, Boolean, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import os
from time import sleep

Base = declarative_base()


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String)
    hashed_password = Column(String)
    role = Column(String)
    account_verified = Column(Boolean)
    name = Column(String)
    login_fail_count = Column(Integer)
    foreign_user_id = Column(String)


# JSON encoding of price
# {
#   price: '123.45',
#   currency_code: 'USD',
# }
class Event(Base):
    __tablename__ = "event"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String)
    cent_price = Column(Integer)
    currency_code = Column(String)
    time = Column(TIMESTAMP)
    number_of_tickets = Column(Integer)
    organizer_id = Column(Integer, ForeignKey("user.id"))


class ResoldEvent(Base):
    __tablename__ = "resold_event"
    __table_args__ = (
        PrimaryKeyConstraint('seller_id', 'event_id'),
    )
    seller_id = Column(Integer, ForeignKey("user.id"))
    event_id = Column(Integer, ForeignKey("event.id"))
    number_of_tickets = Column(Integer)


class SoldTicket(Base):
    __tablename__ = "sold_ticket"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("event.id"))
    buyer_id = Column(Integer, ForeignKey("buyer.id"))
    seller_id = Column(Integer, ForeignKey("user.id"))


class Buyer(Base):
    __tablename__ = "buyer"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    phone = Column(String)
    email = Column(String)


sql_connect = "sqlite:///:memory:"  # Unit test only. For some reason this fails when handling real http requests.
# sql_connect = 'postgresql://postgres:mysecretpassword@localhost/template1'
if "DATABASE_URL" in os.environ:
    sql_connect = os.environ["DATABASE_URL"]
    sleep(2)  # Give external database time to accept connections


# engine = create_engine(sql_connect, echo=True)
engine = create_engine(sql_connect,
    connect_args={"check_same_thread": False},  # Maybe turn this off for Postgres
    poolclass=StaticPool)  # Maybe turn this off for Postgres
engine.execute('pragma foreign_keys=ON')
Base.metadata.create_all(engine)
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)


# For testing
def get_db_session():
    return DBSession()


# For testing
def recreate_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
