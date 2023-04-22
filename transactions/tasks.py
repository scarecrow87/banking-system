from django.utils import timezone

# from celery.decorators import task

from accounts.models import UserBankAccount
from transactions.constants import INTEREST, REPAYMENT
from transactions.models import Transaction, SavingTransaction, LoanTransaction
from celery import shared_task
from .models import UserBankAccount


@shared_task
def calculate_interest_on_saving_accounts():
    print("--- 1/2 Task calculate_interest_on_saving_accounts task in proccess ! ---")
    accounts = UserBankAccount.objects.filter(
        account_type__is_saving_account=True
    ).select_related('account_type')
    created_transactions = []
    updated_accounts = []
    for account in accounts:
        interest = account.account_type.calculate_interest()
        account.balance += interest
        account.save()
        transaction_obj = SavingTransaction(
            account=account,
            transaction_type=INTEREST,
            amount=interest,
            balance_after_transaction=account.balance
        )
        created_transactions.append(transaction_obj)
        updated_accounts.append(account)
    if created_transactions:
        SavingTransaction.objects.bulk_create(created_transactions)
    if updated_accounts:
        UserBankAccount.objects.bulk_update(
            updated_accounts, ['balance']
        )


@shared_task
def calculate_loan_repayment():
    print("--- 2/2 Task calculate_loan_repayment task in proccess ! ---")
    accounts = UserBankAccount.objects.filter(
        account_type__is_loan=True
    ).select_related('account_type')
    created_transactions = []
    updated_accounts = []
    for account in accounts:
        if account.account_type.is_loan:
            if (account.repayment < round(account.account_type.loan_expected_repayment(), 2)):
                # print(account.account_type.loan_interest())
                loan_interest_repayment = round(account.account_type.loan_interest(), 2)
                if ((account.repayment + loan_interest_repayment) > round(
                        account.account_type.loan_expected_repayment(), 2)):
                    loan_interest_repayment = round(account.account_type.loan_expected_repayment(),
                                                    2) - account.repayment
                account.repayment += loan_interest_repayment
                updated_accounts.append(account)

                account = account.user.accounts.first()
                account.balance -= loan_interest_repayment
                account.save()
                transaction_obj = Transaction(
                    account=account,
                    transaction_type=REPAYMENT,
                    amount=-loan_interest_repayment,
                    balance_after_transaction=account.balance
                )
                created_transactions.append(transaction_obj)
                updated_accounts.append(account)
    if created_transactions:
        LoanTransaction.objects.bulk_create(created_transactions)
        Transaction.objects.bulk_create(created_transactions)
    if updated_accounts:
        UserBankAccount.objects.bulk_update(
            updated_accounts, ['balance', 'repayment']
        )
# @task(name="calculate_interest")
# def calculate_interest():
#     print("What theeee fuck")
#     accounts = UserBankAccount.objects.filter(
#         balance__gt=0,
#         interest_start_date__gte=timezone.now(),
#         initial_deposit_date__isnull=False
#     ).select_related('account_type')
#
#     this_month = timezone.now().month
#
#     created_transactions = []
#     updated_accounts = []
#
#     for account in accounts:
#         if this_month in account.get_interest_calculation_months():
#             interest = account.account_type.calculate_interest(
#                 account.balance
#             )
#             account.balance += interest
#             account.save()
#
#             transaction_obj = Transaction(
#                 account=account,
#                 transaction_type=INTEREST,
#                 amount=interest
#             )
#             created_transactions.append(transaction_obj)
#             updated_accounts.append(account)
#
#     if created_transactions:
#         Transaction.objects.bulk_create(created_transactions)
#
#     if updated_accounts:
#         UserBankAccount.objects.bulk_update(
#             updated_accounts, ['balance']
#         )
