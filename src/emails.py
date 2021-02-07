import smtplib
from validate_email import validate_email
from exceptions import (
    InvalidEmailAddress
)
from itsdangerous import URLSafeTimedSerializer
import os


def register(email):
    valid = validate_email(email_address=email, check_mx=False)
    if not valid:
        raise InvalidEmailAddress
    serializer = URLSafeTimedSerializer(os.environ["SECRET_KEY"])
    code = serializer.dumps(email, salt=os.environ['SECURITY_PASSWORD_SALT'])
    app_url = os.environ['APP_URL']  # http://localhost:5000
    activate_url = f"{app_url}/activate/{code}"

    # server = smtplib.SMTP('localhost', 1025)
    server = smtplib.SMTP(os.environ["SMTP_SERVER"], os.environ["SMTP_PORT"])
    server.ehlo()
    server.login('', '')

    sent_from = 'no_reply@tickets.com'
    to = email
    subject = 'Activate your account please.'
    body = f'Please activate by clicking' \
           f' {activate_url}'
    email_text = f"""\
    From: {sent_from}
    To: {to}
    Subject: {subject}

    {body}
    """
    server.sendmail(sent_from, to, email_text)


def activate(code):
    serializer = URLSafeTimedSerializer(os.environ["SECRET_KEY"])
    try:
        email = serializer.loads(
            code,
            salt=os.environ['SECURITY_PASSWORD_SALT'],
            max_age=3600
        )
    except:
        return None
    return email

