from django.urls import path

from .views import UserRegistrationView, LogoutView, UserLoginView, UserValidationView, UserAccountView, \
    UserSavingAccountView, UserRegistrationSavingAccountView, UserLoanView, get_account_type_description

app_name = 'accounts'

urlpatterns = [
    path(
        "login/", UserLoginView.as_view(),
        name="user_login"
    ),
    path(
        "logout/", LogoutView.as_view(),
        name="user_logout"
    ),
    path(
        "register/", UserRegistrationView.as_view(),
        name="user_registration"
    ),
    path(
        "registerSavingAccount/", UserRegistrationSavingAccountView.as_view(),
        name="user_registration_saving_account"
    ),
    path(
        "validate/", UserValidationView.as_view(),
        name="user_validation"
    ),
    path("dashboard/", UserAccountView.as_view(), name="view_accounts"),
    path("savings/", UserSavingAccountView.as_view(), name="view_saving_account"),
    path("loan/", UserLoanView.as_view(), name="user_loan"),
    path('loan/get_account_type_description/', get_account_type_description, name='get_account_type_description'),
    path('savings/get_account_type_description/', get_account_type_description, name='get_account_type_description'),
    path('register/get_account_type_description/', get_account_type_description, name='get_account_type_description'),

]
