from django.urls import path

from .views import UserRegistrationView, LogoutView, UserLoginView, UserAccountView, \
    UserSavingAccountView, UserRegistrationSavingAccountView, UserLoanView, get_account_type_description, UserDetailView

app_name = 'ui'

urlpatterns = [
    path(
        "test/", UserLoginView.as_view(),
        name="test"
 
]
