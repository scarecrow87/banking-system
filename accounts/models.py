from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
)
from django.db import models

from .constants import GENDER_CHOICE
from .managers import UserManager


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True, null=False, blank=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    @property
    def balance(self):
        if hasattr(self, 'account'):
            return self.account.balance
        return 0


class BankAccountType(models.Model):
    name = models.CharField(max_length=128)

    is_debet_account = models.BooleanField(default=True)
    is_saving_account = models.BooleanField(default=False)
    is_loan = models.BooleanField(default=False)

    maximum_withdrawal_amount = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )

    annual_interest_rate = models.DecimalField(
        decimal_places=2,
        max_digits=5,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    interest_calculation_per_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )

    loan_principal = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )

    loan_interest_rate = models.DecimalField(
        decimal_places=2,
        max_digits=5,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    loan_length = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )

    def clean(self):
        # At least one account type must be set
        if not any([self.is_debet_account, self.is_saving_account, self.is_loan]):
            raise ValidationError("At least one account type must be selected.")

        # If is_debit_account is True, maximum_withdrawal_amount is required
        if self.is_debet_account and not self.maximum_withdrawal_amount:
            raise ValidationError("Maximum withdrawal amount is required for debit account.")

        # If is_saving_account is True, maximum_withdrawal_amount,
        # annual_interest_rate, and interest_calculation_per_year are required
        if self.is_saving_account and not all([self.maximum_withdrawal_amount,
                                               self.annual_interest_rate,
                                               self.interest_calculation_per_year]):
            raise ValidationError("Maximum withdrawal amount, annual interest rate, and "
                                  "interest calculation per year are required for saving account.")

        # If is_loan is True, loan_principal, loan_interest_rate, and loan_length are required
        if self.is_loan and not all([self.loan_principal, self.loan_interest_rate, self.loan_length]):
            raise ValidationError("Loan principal, loan interest rate and loan length  are required "
                                  "for loan account.")

        if self.loan_principal is not None and self.loan_interest_rate is not None and self.loan_length is not None:
            requirement = float(self.loan_length) * float(self.loan_interest_rate) * float(self.loan_principal) / 100
            if requirement < float(self.loan_principal) + float(self.loan_principal) * 0.02:
                raise ValidationError(
                    f"Requirement not fulfilled. Loan cannot be created cause repayment ({requirement}) is less than actual loan princicapl.")

    def __str__(self):
        return self.name

    def calculate_interest(self):
        """
        Calculate interest for a saving account.

        This uses a basic interest calculation formula.
        """
        if not self.is_saving_account:
            return None

        p = self.maximum_withdrawal_amount
        r = self.annual_interest_rate
        n = Decimal(self.interest_calculation_per_year)

        # Basic future value formula to calculate interest
        interest = (p * (1 + ((r / 100) / n))) - p

        return round(interest, 2)

    def loan_interest(self):
        """
        Calculate the loan interest rate in percentage.
        """
        if not self.is_loan:
            return None

        P = float(self.loan_principal)
        r = float(self.loan_interest_rate) / 100
        n = float(self.loan_length)

        # M = P * (r * (1 + r) ** n) / ((1 + r) ** n - 1)

        return Decimal(P * r)

    def loan_expected_repayment(self):
        """
        Calculate the loan interest rate in percentage.
        """
        if not self.is_loan:
            return None

        P = float(self.loan_principal)
        r = float(self.loan_interest_rate) / 100
        n = float(self.loan_length)

        return Decimal(P * r * n)


class UserBankAccount(models.Model):
    user = models.ForeignKey(
        User,
        related_name='accounts',
        on_delete=models.CASCADE,
    )
    account_type = models.ForeignKey(
        BankAccountType,
        related_name='accounts',
        on_delete=models.CASCADE
    )
    account_no = models.PositiveIntegerField(unique=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICE)
    birth_date = models.DateField(null=True, blank=True)

    saving_goal = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        default=2000
    )

    repayment = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        validators=[MinValueValidator(0)],
        default=0,
        editable=False
    )

    balance = models.DecimalField(
        default=0,
        max_digits=12,
        decimal_places=2
    )
    interest_start_date = models.DateField(
        null=True, blank=True,
        help_text=(
            'The month number that interest calculation will start from'
        )
    )
    initial_deposit_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return str(self.account_no)

    def get_interest_calculation_months(self):
        """
        List of month numbers for which the interest will be calculated

        returns [2, 4, 6, 8, 10, 12] for every 2 months interval
        """
        interval = int(
            12 / self.account_type.interest_calculation_per_year
        )
        start = self.interest_start_date.month
        return [i for i in range(start, 13, interval)]


class UserAddress(models.Model):
    user = models.OneToOneField(
        User,
        related_name='address',
        on_delete=models.CASCADE,
    )
    street_address = models.CharField(max_length=512)
    city = models.CharField(max_length=256)
    postal_code = models.PositiveIntegerField()
    country = models.CharField(max_length=256)

    def __str__(self):
        return self.user.email
