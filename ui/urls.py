from django.urls import path

from accounts.views import UserRegistrationView, LogoutView, UserLoginView, UserAccountView, \
    UserSavingAccountView, UserRegistrationSavingAccountView, UserLoanView, get_account_type_description, UserDetailView
from rest_framework import routers, serializers, viewsets
from django.contrib.auth import get_user_model
User = get_user_model()

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'users', UserViewSet)

app_name = 'ui'

urlpatterns = [
   path('details', UserDetailView.as_view(), name="edit_user"),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls'))
 
]
