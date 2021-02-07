class NotAllowedException(Exception):
    pass


class UnknownItemException(Exception):
    pass


class InitialAdminRoleException(Exception):
    pass


class InvalidTokenException(Exception):
    pass


class InvalidRequestException(Exception):
    pass


class UserAlreadyExistsException(Exception):
    pass


class InvalidEmailAddress(Exception):
    pass


class WrongUsernameOrPassword(Exception):
    pass


class EmailNotValidated(Exception):
    pass


class AccountBlocked(Exception):
    pass


class OneFieldAtATimeException(Exception):
    pass


class RoleCantChangeException(Exception):
    pass


class SoldOutException(Exception):
    pass


class TryingToResellTooManyTicketsException(Exception):
    pass


class RemoveTicketFirstException(Exception):
    pass