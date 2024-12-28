from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

UserModel = get_user_model()


class EmailOrPhoneModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)

        if username is None:
            return None  # If username is still None, return None to indicate authentication failure

        try:
            if "@" in username:
                user = UserModel.objects.get(email=username)
            else:
                user = UserModel.objects.get(phone_number=username)
        except UserModel.DoesNotExist:
            return None  # User does not exist, return None
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user  # Return the user object if password is correct and user can authenticate
        return None  # Explicitly return None if authentication fails
