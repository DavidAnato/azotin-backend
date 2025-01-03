from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Seed the database with a default superuser if one doesn't exist"

    def handle(self, *args, **kwargs):
        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            first_name = "Admin"
            email = "admin@azotin.com"
            phone_number = "1234567890"
            password = "adminpassword"

            User.objects.create_superuser(
                first_name=first_name,
                email=email,
                phone_number=phone_number,
                password=password,
            )
            self.stdout.write(self.style.SUCCESS("Superuser created successfully."))
        else:
            self.stdout.write(self.style.WARNING("Superuser already exists."))
