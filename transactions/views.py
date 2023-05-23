import functools
from io import BytesIO

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Count
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import JsonResponse, HttpResponse
from django.utils.safestring import SafeString
from .constants import TRANSACTION_TYPE_CHOICES

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView
from itertools import chain
from django.shortcuts import HttpResponseRedirect, render
import pandas as pd
from datetime import datetime, timedelta
from django.utils.timezone import make_aware
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (SimpleDocTemplate, Paragraph, PageBreak, Image, Spacer, Table, TableStyle)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import LETTER, inch
from reportlab.graphics.shapes import Line, LineShape, Drawing
from reportlab.lib.colors import Color
from transactions.constants import DEPOSIT, WITHDRAWAL, TRANSFER
from transactions.forms import (
    DepositForm,
    TransactionDateRangeForm,
    WithdrawForm,
    TransferForm
)
from transactions.models import Transaction, SavingTransaction, LoanTransaction
from accounts.models import UserBankAccount
from reportlab.pdfgen import canvas

MONTHS = {
    0: "Jan",
    1: "Feb",
    2: "Mar",
    3: "Apr",
    4: "May",
    5: "June",
    6: "July",
    7: "Aug",
    8: "Sep",
    9: "Oct",
    10: "Nov",
    11: "Dec",
}


class TransactionRepostView(LoginRequiredMixin, ListView):
    template_name = 'transactions/transaction_report.html'
    model = Transaction
    form_data = {}

    def __init__(self):
        super().__init__()
        self.account_id = None

    def get(self, request, *args, **kwargs):
        if request.GET.get("account_id"):
            form = TransactionDateRangeForm(request.GET or None)
            account = UserBankAccount.objects.get(account_no=request.GET.get("account_id"))
            accounts = UserBankAccount.objects.filter(user_id=self.request.user.id)

            if account.user.id == self.request.user.id:
                self.account_id = request.GET.get("account_id")
                if form.is_valid():
                    self.form_data = form.cleaned_data
                daterange = self.form_data.get("daterange")
                if request.GET.get("transactions"):
                    if daterange:
                        if account.account_type.is_debit_account:
                            transactions = Transaction.objects.filter(account_id=account.id,
                                                                      timestamp__date__range=daterange)
                        if account.account_type.is_saving_account:
                            transactions = SavingTransaction.objects.filter(account_id=account.id,
                                                                            timestamp__date__range=daterange)
                        if account.account_type.is_loan:
                            transactions = LoanTransaction.objects.filter(account_id=account.id,
                                                                          timestamp__date__range=daterange)
                    else:
                        if account.account_type.is_debit_account:
                            transactions = Transaction.objects.filter(account_id=account.id)
                        if account.account_type.is_saving_account:
                            transactions = SavingTransaction.objects.filter(account_id=account.id)
                        if account.account_type.is_loan:
                            transactions = LoanTransaction.objects.filter(account_id=account.id)
                else:
                    if daterange:
                        if account.account_type.is_debit_account:
                            transactions = Transaction.objects.filter(account_id=account.id,
                                                                      timestamp__date__range=daterange)[:10]
                        if account.account_type.is_saving_account:
                            transactions = SavingTransaction.objects.filter(account_id=account.id,
                                                                            timestamp__date__range=daterange)[:10]
                        if account.account_type.is_loan:
                            transactions = LoanTransaction.objects.filter(account_id=account.id,
                                                                          timestamp__date__range=daterange)[:10]
                    else:
                        if account.account_type.is_debit_account:
                            transactions = Transaction.objects.filter(account_id=account.id)[:10]
                        if account.account_type.is_saving_account:
                            transactions = SavingTransaction.objects.filter(account_id=account.id)[:10]
                        if account.account_type.is_loan:
                            transactions = LoanTransaction.objects.filter(account_id=account.id)[:10]

                context = self.get_context_data(object_list=transactions)
                context['account_balance'] = account.balance
                context['account_no'] = account.account_no
                context['account_type'] = account.account_type
                context['accounts'] = accounts
                context['acc'] = account
                if account.account_type.is_loan:
                    context['expected_repayment'] = float(account.account_type.loan_interest_rate) * float(
                        account.account_type.loan_principal) * float(account.account_type.loan_length) / 100
                for account in accounts:
                    if account.account_type.is_saving_account:
                        context["saving_goal"] = account.saving_goal
                        context["interest_rate"] = account.account_type.annual_interest_rate
                        context['saving_goal_fulfilment'] = account.balance / account.saving_goal * 100
                        if account.balance / account.saving_goal * 100 > 100:
                            context['saving_goal_fulfilment'] = 100
                return render(request, self.template_name, context=context)
            else:
                return HttpResponseRedirect("/accounts/dashboard/")

        else:
            return HttpResponseRedirect("/accounts/dashboard/")


class SavingsTransactionRepostView(LoginRequiredMixin, ListView):
    template_name = 'transactions/transaction_report_savings.html'
    model = SavingTransaction
    form_data = {}

    def __init__(self):
        super().__init__()
        self.account_id = None

    def get(self, request, *args, **kwargs):
        if request.GET.get("account_id"):
            form = TransactionDateRangeForm(request.GET or None)
            account = UserBankAccount.objects.get(account_no=request.GET.get("account_id"))
            if account.user.id == self.request.user.id:
                self.account_id = request.GET.get("account_id")
                if form.is_valid():
                    self.form_data = form.cleaned_data
                transactions = self.get_queryset()
                context = self.get_context_data(object_list=transactions)
                context['account_balance'] = account.balance
                return render(request, self.template_name, context=context)
            else:
                return HttpResponseRedirect("/accounts/dashboard/")

        else:
            return HttpResponseRedirect("/accounts/dashboard/")

    def get_queryset(self):
        account = UserBankAccount.objects.get(account_no=self.account_id)
        queryset_to = super().get_queryset().filter(
            account=account
        )

        queryset = queryset_to

        daterange = self.form_data.get("daterange")

        if daterange:
            queryset = queryset.filter(timestamp__date__range=daterange)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'account': UserBankAccount.objects.get(account_no=self.account_id),
            'form': TransactionDateRangeForm(self.request.GET or None)
        })

        return context


class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = 'transactions/transaction_form.html'
    model = Transaction
    title = ''
    success_url = reverse_lazy('transactions:transaction_report')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'account': self.request.user.accounts.first()
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': self.title
        })

        return context


class DepositMoneyView(TransactionCreateMixin):
    form_class = DepositForm
    title = 'Deposit Money to Your Account'

    def get_initial(self):
        initial = {'transaction_type': DEPOSIT}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        account = self.request.user.accounts.first()
        print(amount)
        if not account.initial_deposit_date:
            now = timezone.now()
            # if account.account_type.interest_calculation_per_year != 0:
            #     next_interest_month = int(
            #         12 / account.account_type.interest_calculation_per_year
            #     )
            # else:
            #     next_interest_month = 0
            account.initial_deposit_date = now
            # account.interest_start_date = (
            #         now + relativedelta(
            #     months=+next_interest_month
            # )
            # )

        account.balance += amount
        account.save(
            update_fields=[
                'initial_deposit_date',
                'balance',
                'interest_start_date'
            ]
        )

        messages.success(
            self.request,
            f'{amount}€ was deposited to your account successfully'
        )

        form.account = account
        return super().form_valid(form)


class WithdrawMoneyView(TransactionCreateMixin):
    form_class = WithdrawForm
    title = 'Withdraw Money from Your Account'

    def get_initial(self):
        initial = {'transaction_type': WITHDRAWAL}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        account = self.request.user.accounts.first()

        account.balance -= form.cleaned_data.get('amount')
        account.save(update_fields=['balance'])

        messages.success(
            self.request,
            f'Successfully withdrawn {amount}€ from your account'
        )

        form.account = account
        form.cleaned_data['amount'] = -form.cleaned_data['amount']
        return super().form_valid(form)


class TransferMoneyView(CreateView):
    template_name = 'transactions/transaction_transfer.html'
    form_class = TransferForm
    form_data = {}

    def get(self, request, *args, **kwargs):
        if request.GET.get("account_id"):
            return render(request, self.template_name, {'form': self.form_class})
        return HttpResponseRedirect("/accounts/dashboard/")

    def post(self, request, *args, **kwargs):
        form = TransferForm(request.POST)
        account_id = request.GET.get("account_id")
        account = UserBankAccount.objects.filter(account_no=account_id).first()
        if account:
            if form.is_valid():

                user_to = form.cleaned_data.get("account_to")
                if user_to:
                    amount = form.cleaned_data.get('amount')
                    if account.balance >= amount:
                        account.balance -= amount
                        account.save(update_fields=['balance'])
                        user_to = UserBankAccount.objects.get(account_no=user_to.account_no)
                        user_to.balance += amount
                        user_to.save(update_fields=['balance'])
                        user_from = UserBankAccount.objects.get(account_no=account_id)

                        transaction = Transaction(amount=-form.cleaned_data.get('amount'),
                                                  balance_after_transaction=user_from.balance,
                                                  transaction_type=TRANSFER, account=user_from,
                                                  account_to=user_to
                                                  )

                        transaction_to = Transaction(amount=form.cleaned_data.get('amount'),
                                                     balance_after_transaction=user_to.balance,
                                                     transaction_type=TRANSFER, account=user_to,
                                                     account_to=user_from
                                                     )
                        transaction.save()
                        transaction_to.save()
                        messages.success(
                            self.request,
                            f'Sent {amount}€ to {user_to.account_no}'
                        )
                    else:
                        messages.error(
                            self.request,
                            f'Not enough money'
                        )
                else:
                    messages.error(
                        self.request,
                        f'User doesnt exist'
                    )
            else:
                messages.error(
                    self.request,
                    f'Account isnt belonging to user'
                )
        return render(request, self.template_name, {'form': self.form_class})


class MonthlyReportView(CreateView):
    template_name = 'transactions/monthly_report.html'

    def get(self, request, *args, **kwargs):

        months = Transaction.objects.annotate(month=ExtractMonth('timestamp'),
                                              year=ExtractYear('timestamp'), ).order_by().values('month',
                                                                                                 'year').annotate(
        total=Count('*')).values('month', 'year', 'total').filter(
        account_id=UserBankAccount.objects.filter(user_id=self.request.user.id).first().id)
        for data in months:
            print(data)

            data['month'] = MONTHS[int(data['month'])-1]
            print(data)
        context = {'months': months}
        return render(request, self.template_name, context=context)

    def post(self, request, *args, **kwargs):
        month = request.POST.get("month", 0)
        for key, val in MONTHS.items():  # for name, age in dictionary.iteritems():  (for Python 2.x)
            if val == month:
                month = key + 1
        year = request.POST.get("year", 0)
        months = Transaction.objects.annotate(month=ExtractMonth('timestamp'),
                                              year=ExtractYear('timestamp'), ).order_by().values('month',
                                                                                                 'year').annotate(
            total=Count('*')).values('month', 'year', 'total').filter(
            account_id=UserBankAccount.objects.filter(user_id=self.request.user.id).first().id)
        context = {'months': months}
        account = UserBankAccount.objects.first()

        transactions = Transaction.objects.filter(timestamp__year__gte=year,
                                                  timestamp__month__gte=month,
                                                  timestamp__year__lte=year,
                                                  timestamp__month__lte=month,
                                                  account_id=account.id)

        buffer = BytesIO()



        psHeaderText = ParagraphStyle('Hed0', fontSize=12, alignment=TA_LEFT, borderWidth=3)
        text = 'Monthly Report - ' + MONTHS[int(month)-1]
        paragraphReportHeader = Paragraph(text, psHeaderText)
        elements = []
        elements.append(paragraphReportHeader)

        spacer = Spacer(10, 22)
        elements.append(spacer)
        """
        Create the line items
        """
        d = []
        textData = ["Date", "Type", "Amount"]

        fontSize = 8
        centered = ParagraphStyle(name="centered", alignment=TA_CENTER)
        for text in textData:
            ptext = "<font size='%s'><b>%s</b></font>" % (fontSize, text)
            titlesTable = Paragraph(ptext, centered)
            d.append(titlesTable)
        colorOhkaBlue1 = Color((122.0/255), (180.0/255), (225.0/255), 1)
        colorOhkaGreenLineas = Color((50.0/255), (140.0/255), (140.0/255), 1)
        data = [d]
        lineNum = 1
        formattedLineData = []

        alignStyle = [ParagraphStyle(name="01", alignment=TA_CENTER),
                      ParagraphStyle(name="02", alignment=TA_LEFT),
                      ParagraphStyle(name="03", alignment=TA_CENTER)]

        for item in transactions:
            columnNumber = 0
            transaction_type_string = functools.partial(item._get_FIELD_display,
                                                        field=item._meta.get_field('transaction_type'))()
            date = item.timestamp.strftime("%Y-%m-%d")
            amount = str(item.amount) + "€"
            print(transaction_type_string, date, item.amount)
            column_data = [date, transaction_type_string, amount]
            for col in column_data:
                ptext = "<font size='%s'>%s</font>" % (fontSize - 1, col)
                p = Paragraph(ptext, alignStyle[columnNumber])
                formattedLineData.append(p)
                columnNumber = columnNumber + 1
            data.append(formattedLineData)
            formattedLineData = []
        table = Table(data, colWidths=[50, 200, 80, 80, 80])
        tStyle = TableStyle([  # ('GRID',(0, 0), (-1, -1), 0.5, grey),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            # ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ("ALIGN", (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, 0), (-1, -1), 1, colorOhkaBlue1),
            ('BACKGROUND', (0, 0), (-1, 0), colorOhkaGreenLineas),])

        table.setStyle(tStyle)
        elements.append(table)
        doc = SimpleDocTemplate(buffer, pagesize=LETTER, bottomup=False, encrypt=request.user.pdf_password)
        doc.multiBuild(elements)
        pdf = buffer.getvalue()
        buffer.close()
        sendMail(request,pdf,month,year)
        return render(request, self.template_name, context=context)


def sendMail(request, pdf, month, year):
    subject = "Monthly report of payments for " + str(MONTHS[int(month)-1]) +" "+ str(year)
    message = "Dear Client, \n Please find enclosed your account statement(s) for the past month. \n We are committed to keeping your money and personal information safe with us, which is why we send all statements automatically encrypted. \n You can view your password in online banking."
    emails = [request.user.email]

    mail = EmailMessage(subject, message, settings.EMAIL_HOST_USER, emails)
    mail.attach('monthly_report_' + MONTHS[int(month)-1] + "_" + request.user.last_name +'.pdf', pdf, 'application/pdf')

    try:
        mail.send(fail_silently=False)
        return HttpResponse("Mail Sent")
    except:
        return HttpResponse("Mail Not Sent")


def get_data(request):
    account = UserBankAccount.objects.get(account_no=request.GET.get("account_id"))

    if account:
        startdate = make_aware(datetime.today())
        enddate = startdate - timedelta(days=110)

        transactions = Transaction.objects.filter(account_id=account.id, timestamp__range=(enddate, startdate))
        df = pd.DataFrame(transactions.values())
        df = df.groupby([df['timestamp'].dt.month]).agg(monthly_amount=('amount', 'sum'),
                                                        negative=('amount', lambda x: x[x < 0].sum()),
                                                        positive=('amount', lambda x: x[x > 0].sum()))

        indexes = df.index.values.tolist()
        indexes.reverse()
        print(indexes)
        months = []
        for i in range(indexes[0], indexes[0] - 5, -1):
            if i not in indexes:
                new_row = pd.DataFrame({'monthly_amount': 0, 'negative': 0, 'positive': 0},
                                       index=[i])
                df = pd.concat([new_row, df.loc[:]])
            print((indexes[0] - i) % 12)
            months.append(MONTHS[(indexes[0] - i - 1) % 12])
        df = df.sort_index()
        print(df)
        chart_data = {"negative_transactions": [-x for x in df['negative'].tolist()],
                      "positive_transactions": [x for x in df['positive'].tolist()],
                      "monthly_amount": [x for x in df['monthly_amount'].tolist()],
                      "labels": months}

        return JsonResponse(chart_data, safe=False)
