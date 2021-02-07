# Events API

## Overview

This is an API for selling and managing event tickets.

### Events

Each event contains the following information:
  * Title
  * Date of the event
  * Number of tickets
  * Price of the ticket
  
### Users overview

Users have the following roles:

* Ticket buyer
* Ticket reseller
* Venue organizer
* Administrator

New users need to verify their account by email. Users should not be able to log in
until this verification is complete. As an alternative, users can log in using either Google or Github.

When a user fails to log in three times in a row, their account should be blocked 
automatically, and only administrators should be able to unblock it.

All user actions can be performed via the API, including authentication.

### Venue organizer

The Venue organizer can 
* Register and log in
* Create, read, update and delete events
* Assign a certain number of tickets being sold by a ticket reseller. 
  For example, if a venue organizer wants to sell 1000 tickets, 
  it can assign 250 tickets for two resellers each. 
  In that case, venue organizers can sell 500 tickets on their own.

### Ticket reseller

The ticket resellers can: 

* Register and log in
* See tickets assigned by venue organizers
* Offer available tickets to be sold to ticket buyers

## Administrator

The administrator can create, read, update and delete:
 * Venue organizers
 * Resellers
 * Buyers information
 * Sold tickets information
 * Unblock blocked users
 
### Buyer

The Buyer cannot register or login. The buyer can pick a ticket from a reseller or venue organizer
and book it. 

## Setup

To run, you will need Python 3.7. Follow these steps to run the tests:

1. Open a terminal in this directory
1. Run ```python3 -m venv venv```
1. Run ```. venv/bin/activate```
1. Run ```pip install -r requirements.txt```
1. Run ```cd src```
1. Run ```mv secrets.yaml.not_ignore secrets.yaml```
1. Run ```python -m unittest discover .```. This will run all the tests.
1. Run 

```bash
export INIT_ADMIN_EMAIL=admin@localmail.com
export ADMIN_PASSWORD=password1
export SECRET_KEY=SECRET_KEY
export SECURITY_PASSWORD_SALT=SECURITY_PASSWORD_SALT
export APP_URL=http://localhost:5000
export SMTP_SERVER=localhost
export SMTP_PORT=1025
python app.py
```

To authenticate with Google or Github you will need to fill secrets.yaml
with appropriate client ID and secret values.

## Usage

If you navigate to http://0.0.0.0:5000/ there is a swagger interface that documents the possible 
commands and parameters.

### Register and login with email

This flow allows a user to register and login with an email address. Start by registering like this:

```bash
curl -X POST "http://0.0.0.0:5000/register" -H  "accept: application/json" -H  "Content-Type: application/json" -d "{  \"email\": \"me@mail.com\",  \"password\": \"password1\",  \"name\": \"ME\",  \"role\": \"organizer\"}"
```

You should then get an email with an activation link. Once you have this you can login like this:

```bash
curl -X POST "http://0.0.0.0:5000/login" -H  "accept: application/json" -H  "Content-Type: application/json" -d "{  \"email\": \"me@mail.com\",  \"password\": \"password1\"}"
```

... this will give you an auth_token. You can then use this to create events like this:

```bash
curl -X POST "http://0.0.0.0:5000/events" -H  "accept: application/json" -H  "access-token: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjozLCJleHAiOjE2MDE0MzU1MTh9.cDwoZ6pSE_JYhC3H3gOiX6Wgp2FvC0JMOkLgN07khlA" -H  "access-type: email" -H  "Content-Type: application/json" -d "{  \"title\": \"A music concert\",  \"price\": \"50\",  \"currency_code\": \"GBP\",  \"time\": \"2021-09-09\",  \"number_of_tickets\": 1000}"
```

### Register and login with Google or Github

This flow allows a user to register and login with a Google or Github account.
For convenience, this API wraps the Oauth2 device authentication flow for Github and Google. You can however
replace this with a web or mobile based flow. To do this you will need to use the client ID (provided in the secrets.yaml file)
with your web or mobile front end. The front end should then provide an access token which we can then use. Without a
frontend, this is the current auth flow that is on offer:

```bash
curl -X GET "http://0.0.0.0:5000/github-device-auth-step-1" -H  "accept: application/json"
```

The output will look like this:

```json
{
  "device_code": "AH-1Ng2skjhsfdjhkfsdhjkfsdhjkfssjfksdjsfljfsklfdj",
  "user_code": "CPWY-AAAA",
  "expires_in": 1800,
  "interval": 5,
  "verification_url": "https://www.google.com/device"
}
```

Navigate to https://www.google.com/device in your web browser, enter the user code and follow the instructions to 
associate it with a real google account. Then copy the device code into another request like this:

```bash
curl -X POST "http://0.0.0.0:5000/google-device-auth-step-2" -H  "accept: application/json" -H  "Content-Type: application/json" -d "{  \"device_code\": \"AH-1Ng2skjhsfdjhkfsdhjkfsdhjkfssjfksdjsfljfsklfdj\"}""
```

The output will look like this:

```json
{
  "access_token": "sdfsdfkljfdsjlkfdsklfsdjlkfdsjkl"
}
```

You can then use this access token to perform operations like this:

```bash
curl -X GET "http://0.0.0.0:5000/myself" -H  "accept: application/json" -H  "access-token: sdfsdfkljfdsjlkfdsklfsdjlkfdsjkl" -H  "access-type: google"
```




