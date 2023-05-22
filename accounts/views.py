import datetime

from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from django.shortcuts import HttpResponseRedirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import RedirectView
import requests
import random
from banking_system.settings import ACCOUNT_NUMBER_START_FROM
from transactions.constants import DEPOSITTSA, WITHDRAWALFSA, LOAN, REPAYMENT
from transactions.models import Transaction, SavingTransaction, LoanTransaction
from .forms import UserRegistrationForm, UserAddressForm, LoanForm
from .models import User
from django.contrib.auth import authenticate
from django.views.generic import TemplateView
from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import SavingAccountForm
from .models import UserBankAccount, BankAccountType
from decimal import Decimal
from accounts.credentials_api import password as password_api
from accounts.credentials_api import username as username_api

User = get_user_model()


class UserRegistrationView(TemplateView):
    model = User
    form_class = UserRegistrationForm
    template_name = 'accounts/user_registration.html'

    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            return HttpResponseRedirect(
                reverse_lazy('transactions:transaction_report')
            )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        registration_form = UserRegistrationForm(self.request.POST)
        address_form = UserAddressForm(self.request.POST)

        if registration_form.is_valid() and address_form.is_valid():
            user = registration_form.save()
            address = address_form.save(commit=False)
            address.user = user
            address.save()

            url = 'https://otp-tp.herokuapp.com/api/auth/token'
            response = requests.post(url, auth=(username_api, password_api))
            token = response.text

            url = 'https://otp-tp.herokuapp.com/user'
            payload = {"email": user.email}
            requests.post(url, json=payload,headers={'Content-Type': 'application/json',
                                           'Authorization': 'Bearer {}'.format(token)})
            messages.success(
                self.request,
                (
                    f'Thank You For Creating A Bank Account. '
                    f'Your Account Number is {user.accounts.first().account_no}. '
                )
            )
            return HttpResponseRedirect(
                reverse_lazy('accounts:user_validation')
            )

        return self.render_to_response(
            self.get_context_data(
                registration_form=registration_form,
                address_form=address_form
            )
        )

    def get_context_data(self, **kwargs):
        if 'registration_form' not in kwargs:
            kwargs['registration_form'] = UserRegistrationForm()
        if 'address_form' not in kwargs:
            kwargs['address_form'] = UserAddressForm()

        return super().get_context_data(**kwargs)

class UserLoginView(LoginView):
    template_name = 'accounts/user_login.html'

    def post(self, request, *args, **kwargs):
        user = authenticate(username=request.POST["username"], password=request.POST["password"])
        if user is not None:
            request.session["email"] = request.POST["username"]
            email = request.session["email"]
            send_otp(email)
            return HttpResponseRedirect(
                reverse_lazy('accounts:user_validation')
            )
        else:
            messages.error(
                self.request,
                (
                    f'Wrong credentials. '
                )
            )
            return HttpResponseRedirect(
                reverse_lazy('accounts:user_login')
            )


class LogoutView(RedirectView):
    pattern_name = 'home'

    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            logout(self.request)
        return super().get_redirect_url(*args, **kwargs)


class UserValidationView(TemplateView):
    template_name = 'accounts/user_otp.html'

    def get(self, request, *args, **kwargs):

        if not request.session.get("email"):
            return HttpResponseRedirect(
                reverse_lazy('accounts:user_login')
            )
        if not User.objects.get(email=request.session["email"]).is_authenticated:
            return HttpResponseRedirect(
                reverse_lazy('accounts:user_login')
            )

        return render(request, 'accounts/user_otp.html')

    def post(self, request, *args, **kwargs):
        otp = request.POST.get("otp", 0)
        if otp == 0:
            email = request.session["email"]
            send_otp(email)
            return render(request, 'accounts/user_otp.html')

        if len(otp) < 6:
            messages.error(
                self.request,
                (
                    f'Wrong OTP - length. '
                )
            )
            return render(request, 'accounts/user_otp.html')

        url = 'https://otp-tp.herokuapp.com/api/auth/token'

        response = requests.post(url, auth=(username_api, password_api))
        token = response.text

        url = 'https://otp-tp.herokuapp.com/user/otp/validate/' + request.session["email"] + "?otp=" + otp
        r = requests.get(url, headers={'Content-Type': 'application/json',
                                                  'Authorization': 'Bearer {}'.format(token)})

        if r.status_code == 401:
            messages.error(
                self.request,
                (
                    f'Wrong OTP. '
                )
            )
            return render(request, 'accounts/user_otp.html')

        login(self.request, User.objects.get(email=request.session["email"]))
        return HttpResponseRedirect(

            reverse_lazy('transactions:deposit_money')

        )


class UserAccountView(TemplateView):
    template_name = 'transactions/transaction_report.html'

    def get(self, request, *args, **kwargs):
        user = User.objects.get(email=request.session["email"])
        accounts = UserBankAccount.objects.filter(user_id=user.id, account_type__is_debet_account=True).first()
        return HttpResponseRedirect("/transactions/report/?account_id=" + str(accounts.account_no))


def send_otp(email):
    url = 'https://otp-tp.herokuapp.com/api/auth/token'
    response = requests.post(url, auth=(username_api, password_api))
    token = response.text

    url_get = 'https://otp-tp.herokuapp.com/user/otp/generate/'+ email
    response = requests.get(url_get, headers={'Content-Type':'application/json',
               'Authorization': 'Bearer {}'.format(token)})


class UserRegistrationSavingAccountView(View):
    template_name = 'accounts/create_saving_account.html'
    form_class = SavingAccountForm

    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})


class UserSavingAccountView(TemplateView):
    template_name = 'transactions/transaction_savings.html'

    def get(self, request, *args, **kwargs):
        accountDebet = self.request.user.accounts.first()
        accountSaving = self.request.user.accounts.filter(account_type__is_saving_account=True).first()
        if (accountSaving == None):
            savings_view = UserRegistrationSavingAccountView.as_view()
            return savings_view(request)
        balance = accountDebet.balance
        savings_balance = accountSaving.balance
        interest_rate = accountSaving.account_type.annual_interest_rate
        context = {
            'account_no': accountSaving.account_no,
            'balance': balance,
            'savings_balance': savings_balance,
            'interest_rate': interest_rate,
        }
        if savings_balance == 0:
            context['can_delete_saving_acc'] = True
        return render(request, 'transactions/transaction_savings.html', context)

    def post(self, request, *args, **kwargs):
        user = request.user

        if UserBankAccount.objects.filter(user_id=user.id, account_type__is_saving_account=True).exists() is not True:
            form = SavingAccountForm(request.POST)
            if form.is_valid():

                if form.cleaned_data['birth_date'] != self.request.user.accounts.first().birth_date:
                    messages.error(request, "Credentials are invalid!")
                    return HttpResponseRedirect("/accounts/savings/")
                # Save the new saving account
                saving_account = form.save(commit=False)
                saving_account.interest_start_date = datetime.datetime.now()
                saving_account.account_no = ACCOUNT_NUMBER_START_FROM + (
                        random.randint(1, 1000) * random.randint(1, 1000))
                saving_account.user = self.request.user
                saving_account.save()

                return HttpResponseRedirect("/accounts/dashboard/")

            else:
                # If the request method is not POST, display the form
                form = SavingAccountForm()

            return render(request, 'accounts/create_saving_account.html', {'form': form})

        ###
        if request.POST.get('deleting_saving_acc') == 'true':
            user_saving_acc = self.request.user.accounts.filter(account_type__is_saving_account=True).first()
            user_saving_acc.delete()
            return HttpResponseRedirect("/accounts/dashboard/")

        accountDebet = self.request.user.accounts.first()
        accountSaving = self.request.user.accounts.filter(account_type__is_saving_account=True).first()
        if 'depositToSavingAcc' in request.POST:
            amount = Decimal(request.POST.get('depositToSavingAcc'))

            # if not account.initial_deposit_date:
            #     now = timezone.now()
            #     if account.account_type.interest_calculation_per_year != 0:
            #         next_interest_month = int(
            #             12 / account.account_type.interest_calculation_per_year
            #         )
            #     else:
            #         next_interest_month = 0
            #     account.initial_deposit_date = now
            #     account.interest_start_date = (
            #             now + relativedelta(
            #         months=+next_interest_month
            #     )
            #     )

            if amount <= 0:
                messages.error(request, "Invalid operation.")
            elif accountDebet.balance >= amount:
                accountDebet.balance -= amount
                accountSaving.balance += amount
                accountDebet.save(
                    update_fields=[
                        'balance'
                    ]
                )
                accountSaving.save(
                    update_fields=[
                        'balance'
                    ]
                )

                messages.success(
                    self.request,
                    f'{amount}$ was deposited to your saving account from debet account successfully'
                )

                created_transactions = []
                created_transactionsSavings = []
                transaction_obj = Transaction(
                    account=accountDebet,
                    transaction_type=DEPOSITTSA,
                    amount=-amount,
                    balance_after_transaction=accountDebet.balance
                )
                transaction_objSavings = Transaction(
                    account=accountSaving,
                    transaction_type=DEPOSITTSA,
                    amount=amount,
                    balance_after_transaction=accountSaving.balance
                )
                created_transactions.append(transaction_obj)
                created_transactionsSavings.append(transaction_objSavings)
                if created_transactions:
                    Transaction.objects.bulk_create(created_transactions)
                    SavingTransaction.objects.bulk_create(created_transactionsSavings)

            else:
                messages.error(request, "Not enough money on debet account!")

            balance = accountDebet.balance
            savings_balance = accountSaving.balance
            interest_rate = accountSaving.account_type.annual_interest_rate
            context = {
                'account_no': accountDebet.account_no,
                'balance': balance,
                'savings_balance': savings_balance,
                'interest_rate': interest_rate,
            }

            return render(request, 'transactions/transaction_savings.html', context)
        elif 'withdrawFromSavingAccount' in request.POST:
            amount = Decimal(request.POST.get('withdrawFromSavingAccount'))

            if amount <= 0:
                messages.error(request, "Invalid operation.")
            elif accountSaving.balance >= amount:
                accountSaving.balance -= amount
                accountDebet.balance += amount
                accountDebet.save(
                    update_fields=[
                        'balance'
                    ]
                )
                accountSaving.save(
                    update_fields=[
                        'balance'
                    ]
                )

                messages.success(
                    self.request,
                    f'{amount}$ was deposited to your debet account from saving account successfully'
                )

                created_transactions = []
                created_transactionsSavings = []
                transaction_obj = Transaction(
                    account=accountDebet,
                    transaction_type=WITHDRAWALFSA,
                    amount=amount,
                    balance_after_transaction=accountDebet.balance
                )
                transaction_objSavings = Transaction(
                    account=accountSaving,
                    transaction_type=WITHDRAWALFSA,
                    amount=-amount,
                    balance_after_transaction=accountSaving.balance
                )
                created_transactions.append(transaction_obj)
                created_transactionsSavings.append(transaction_objSavings)
                if created_transactions:
                    Transaction.objects.bulk_create(created_transactions)
                    SavingTransaction.objects.bulk_create(created_transactionsSavings)

            else:
                messages.error(request, "Not enough money on your saving account!")

            balance = accountDebet.balance
            savings_balance = accountSaving.balance
            interest_rate = accountSaving.account_type.annual_interest_rate
            context = {
                'account_no': accountSaving.account_no,
                'balance': balance,
                'savings_balance': savings_balance,
                'interest_rate': interest_rate,
            }
            return render(request, 'transactions/transaction_savings.html', context)
        else:
            messages.error(request, "Invalid operation.")
            balance = accountDebet.balance
            savings_balance = accountSaving.balance
            interest_rate = accountSaving.account_type.annual_interest_rate
            context = {
                'account_no': accountSaving.account_no,
                'balance': balance,
                'savings_balance': savings_balance,
                'interest_rate': interest_rate,
            }
            return render(request, 'transactions/transaction_savings.html', context)


class UserLoanView(View):
    loan_create_template = 'accounts/create_loan.html'
    form_class = LoanForm

    loan_template_name = 'accounts/transaction_loan.html'

    def get(self, request):
        user_loan = self.request.user.accounts.filter(account_type__is_loan=True).first()
        if (user_loan == None):
            form = self.form_class()
            return render(request, self.loan_create_template, {'form': form})
        else:

            if user_loan.repayment >= round(user_loan.account_type.loan_expected_repayment(), 2):
                can_delete_loan = True
            else:
                can_delete_loan = False

            context = {
                'loan_no': user_loan.account_no,
                'loan_principal': user_loan.account_type.loan_principal,
                'loan_expected_repayment': round(user_loan.account_type.loan_expected_repayment(), 2),
                'loan_repayment': user_loan.repayment,
                'loan_interest_rate': user_loan.account_type.loan_interest_rate,
                'loan_length': user_loan.account_type.loan_length,
                "can_delete_loan": can_delete_loan,
            }
            return render(request, 'transactions/transaction_loan.html', context)

    def post(self, request, *args, **kwargs):
        user = request.user

        if UserBankAccount.objects.filter(user_id=user.id, account_type__is_loan=True).exists() is not True:
            form = LoanForm(request.POST)
            if form.is_valid():

                if form.cleaned_data['birth_date'] != self.request.user.accounts.first().birth_date:
                    messages.error(request, "Credentials are invalid!")
                    return HttpResponseRedirect("/accounts/loan/")
                # Save the new saving account
                new_loan = form.save(commit=False)
                new_loan.interest_start_date = datetime.datetime.now()
                new_loan.account_no = ACCOUNT_NUMBER_START_FROM + (
                        random.randint(1, 1000) * random.randint(1, 1000))
                new_loan.user = self.request.user
                new_loan.save()

                accountDebet = self.request.user.accounts.first()
                accountDebet.balance += new_loan.account_type.loan_principal
                accountDebet.save(
                    update_fields=[
                        'balance'
                    ]
                )

                created_transactions = []
                created_transactionsLoan = []
                transaction_obj = Transaction(
                    account=accountDebet,
                    transaction_type=LOAN,
                    amount=new_loan.account_type.loan_principal,
                    balance_after_transaction=accountDebet.balance
                )
                transaction_objLoan = Transaction(
                    account=new_loan,
                    transaction_type=LOAN,
                    amount=-new_loan.account_type.loan_principal,
                    balance_after_transaction=-new_loan.balance
                )
                created_transactions.append(transaction_obj)
                created_transactionsLoan.append(transaction_objLoan)
                if created_transactions:
                    Transaction.objects.bulk_create(created_transactions)
                    LoanTransaction.objects.bulk_create(created_transactionsLoan)

                return HttpResponseRedirect("/accounts/dashboard/")

            else:
                # If the request method is not POST, display the form
                form = LoanForm()

            return render(request, 'accounts/create_loan.html', {'form': form})
        else:
            if request.POST.get('deleting_loan') == 'true':
                user_loan = self.request.user.accounts.filter(account_type__is_loan=True).first()
                user_loan.delete()
                return HttpResponseRedirect("/accounts/dashboard/")
            repayment = Decimal(request.POST.get('insta_repayment'))
            if repayment:
                user_debet_account = self.request.user.accounts.first()
                user_loan = self.request.user.accounts.filter(account_type__is_loan=True).first()
                if user_loan.repayment < round(user_loan.account_type.loan_expected_repayment(), 2):
                    need_to_repay = round(user_loan.account_type.loan_expected_repayment(), 2) - user_loan.repayment
                    if repayment > need_to_repay:
                        messages.error(request, f"You only need to pay {need_to_repay}.")
                    else:
                        if (user_debet_account.balance >= repayment):
                            user_loan.repayment += repayment
                            user_debet_account.balance -= repayment
                            user_debet_account.save(
                                update_fields=[
                                    'balance'
                                ]
                            )
                            user_loan.save(
                                update_fields=[
                                    'repayment'
                                ]
                            )

                            created_transactions = []
                            created_transactionsLoan = []
                            transaction_obj = Transaction(
                                account=user_debet_account,
                                transaction_type=REPAYMENT,
                                amount=-repayment,
                                balance_after_transaction=user_debet_account.balance
                            )
                            transaction_objLoan = Transaction(
                                account=user_loan,
                                transaction_type=REPAYMENT,
                                amount=repayment,
                                balance_after_transaction=user_loan.balance
                            )
                            created_transactions.append(transaction_obj)
                            created_transactionsLoan.append(transaction_objLoan)
                            if created_transactions:
                                Transaction.objects.bulk_create(created_transactions)
                                LoanTransaction.objects.bulk_create(created_transactionsLoan)
                                messages.success(
                                    self.request,
                                    f'{repayment}$ was paid back to bank.'
                                )

                            else:
                                messages.error(request, "Not enough money on debet account!")

                        print("Nice")
                else:
                    messages.success(
                        self.request,
                        "You already paid full loan. You can now create another loan if you want by deleting this one."
                    )

        return HttpResponseRedirect("/accounts/loan/")


def get_account_type_description(request):
    account_type_id = request.GET.get('name')
    account_type = BankAccountType.objects.filter(id=account_type_id).first()
    description = account_type.description
    return HttpResponse(description)
