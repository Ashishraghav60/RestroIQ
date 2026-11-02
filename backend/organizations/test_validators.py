from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from .models import Organization
from .validators import validate_currency_code, validate_timezone


class ValidatorFunctionTests(SimpleTestCase):

    def test_valid_currency_codes_pass(self):
        for code in ("INR", "USD", "AED"):
            validate_currency_code(code)

    def test_invalid_currency_codes_fail(self):
        for code in ("inr", "RS", "RUPEES", "12A", ""):
            with self.assertRaises(ValidationError):
                validate_currency_code(code)

    def test_valid_timezones_pass(self):
        for name in ("Asia/Kolkata", "Asia/Dubai", "UTC"):
            validate_timezone(name)

    def test_invalid_timezones_fail(self):
        for name in ("Mars/Phobos", "India", "../etc/passwd"):
            with self.assertRaises(ValidationError):
                validate_timezone(name)


class OrganizationValidationTests(TestCase):

    def test_bad_currency_is_rejected_by_full_clean(self):
        org = Organization(name="X", slug="x", default_currency="rupees")
        with self.assertRaises(ValidationError) as ctx:
            org.full_clean()
        self.assertIn("default_currency", ctx.exception.message_dict)

    def test_bad_timezone_is_rejected_by_full_clean(self):
        org = Organization(name="X", slug="x", timezone="Mars/Phobos")
        with self.assertRaises(ValidationError) as ctx:
            org.full_clean()
        self.assertIn("timezone", ctx.exception.message_dict)

    def test_default_organization_values_are_valid(self):
        org = Organization(name="X", slug="x")
        org.full_clean()