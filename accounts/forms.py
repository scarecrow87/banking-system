from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from .models import User, BankAccountType, UserBankAccount, UserAddress
from .constants import GENDER_CHOICE


class DateInput(forms.DateInput):
    input_type = 'date'


class UserAddressForm(forms.ModelForm):

    class Meta:
        model = UserAddress
        fields = [
            'street_address',
            'city',
            'postal_code',
            'country'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': (
                    'py-2 px-3 pr-11 block w-full border border-gray-200 shadow-sm text-sm rounded-lg focus:border-blue-500 focus:ring-blue-500 dark:bg-slate-900 dark:border-gray-700 dark:text-gray-400'
                )
            })

class UserUpdateForm(forms.ModelForm):

    gender = forms.ChoiceField(choices=GENDER_CHOICE)
    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': (
                    'py-2 px-3 pr-11 block w-full border border-gray-200 shadow-sm text-sm rounded-lg focus:border-blue-500 focus:ring-blue-500 dark:bg-slate-900 dark:border-gray-700 dark:text-gray-400'
                )
            })

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            gender = self.cleaned_data.get('gender')
            birth_date = self.cleaned_data.get('birth_date')

            # assuming a user has exactly one UserBankAccount related object
            user_bank_account = UserBankAccount.objects.get(user=user)
            user_bank_account.gender = gender
            user_bank_account.birth_date = birth_date
            user_bank_account.save()
            user.save()
        return user

class UserRegistrationForm(UserCreationForm):
    account_type = forms.ModelChoiceField(
        queryset=BankAccountType.objects.all()
    )
    gender = forms.ChoiceField(choices=GENDER_CHOICE)
    birth_date = forms.DateField(widget=DateInput)

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'password1',
            'password2',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter account types to show only those with is_saving_account=False
        self.fields['account_type'].queryset = BankAccountType.objects.filter(is_debet_account=True)

        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': (
                    'py-2 px-3 pr-11 block w-full border border-gray-200 shadow-sm text-sm rounded-lg focus:border-blue-500 focus:ring-blue-500 dark:bg-slate-900 dark:border-gray-700 dark:text-gray-400'
                )
            })

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            account_type = self.cleaned_data.get('account_type')
            gender = self.cleaned_data.get('gender')
            birth_date = self.cleaned_data.get('birth_date')

            UserBankAccount.objects.create(
                user=user,
                gender=gender,
                birth_date=birth_date,
                account_type=account_type,
                account_no=(
                        user.id +
                        settings.ACCOUNT_NUMBER_START_FROM
                )
            )
        return user


class SavingAccountRegistrationForm(UserCreationForm):  # *LIDL* ? solution so far for SavingAccountRegistration
    account_type = forms.ModelChoiceField(
        BankAccountType.objects.filter(is_saving_account=True)
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter account types to show only those with is_saving_account=False
        self.fields['account_type'].queryset = BankAccountType.objects.filter(is_saving_account=True)

        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': (
                    'py-2 px-3 pr-11 block w-full border border-gray-200 shadow-sm text-sm rounded-lg focus:border-blue-500 focus:ring-blue-500 dark:bg-slate-900 dark:border-gray-700 dark:text-gray-400'
                )
            })

    @transaction.atomic
    def save(self, commit=True):
        if commit:
            account_type = self.cleaned_data.get('account_type')
            UserBankAccount.objects.create(
                account_type=account_type,
                account_no=(
                        1 +
                        settings.ACCOUNT_NUMBER_START_FROM
                )
            )


class SavingAccountForm(forms.ModelForm):
    class Meta:
        model = UserBankAccount
        fields = ['account_type','saving_goal']
        widgets = {'birth_date' : DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['account_type'].queryset = BankAccountType.objects.filter(is_saving_account=True)

        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': (
                    'py-2 px-3 pr-11 block w-full border border-gray-200 shadow-sm text-sm rounded-lg focus:border-blue-500 focus:ring-blue-500 dark:bg-slate-900 dark:border-gray-700 dark:text-gray-400'
                )
            })


class LoanForm(forms.ModelForm):
    class Meta:
        model = UserBankAccount
        fields = ['account_type']
        widgets = {'birth_date': DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['account_type'].queryset = BankAccountType.objects.filter(is_loan=True)

        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': (
                    'py-3 px-4 block w-full border border-gray-200 rounded-md text-sm focus:border-blue-500 focus:ring-blue-500 sm:p-4 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-400'
                )
            })
