from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

# Three uppercase letters, like INR, USD, AED.
# This checks the format only. It does not check against the full ISO 4217 list.
validate_currency_code = RegexValidator(
    regex=r"^[A-Z]{3}$",
    message="Enter a 3-letter uppercase currency code, for example INR.",
)


def validate_timezone(value):
    """Reject names that are not real IANA timezones, e.g. 'Mars/Phobos'."""
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValidationError(
            "'%(value)s' is not a valid timezone name, for example Asia/Kolkata.",
            params={"value": value},
        )