from django.contrib.auth.models import BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, email, first_name, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('The Phone Number field must be set')
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(phone_number=phone_number, email=email, first_name=first_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, email, first_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone_number, email, first_name, password, **extra_fields)

    def get_by_natural_key(self, identifier):
        if '@' in identifier:
            return self.get(email=identifier)
        return self.get(phone_number=identifier)
