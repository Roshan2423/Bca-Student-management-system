from django.core.management.base import BaseCommand
from courses.models import populate_bca_subjects

class Command(BaseCommand):
    def handle(self, *args, **options):
        populate_bca_subjects()