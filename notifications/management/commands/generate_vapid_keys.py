"""Generate a Web Push VAPID key pair without writing secrets to disk."""
from base64 import urlsafe_b64encode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand, CommandError


def _base64url(value):
    return urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


class Command(BaseCommand):
    help = 'Generate a VAPID key pair for browser push notifications.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subject',
            default='mailto:admin@example.com',
            help='VAPID contact subject, for example mailto:admin@example.com.',
        )

    def handle(self, *args, **options):
        subject = options['subject'].strip()
        if not (subject.startswith('mailto:') or subject.startswith('https://')):
            raise CommandError('The subject must start with mailto: or https://.')

        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        private_key_bytes = private_key.private_numbers().private_value.to_bytes(32, 'big')

        self.stdout.write('Add the following values to the deployment environment:')
        self.stdout.write('WEB_PUSH_ENABLED=True')
        self.stdout.write(f'VAPID_PUBLIC_KEY={_base64url(public_key)}')
        self.stdout.write(f'VAPID_PRIVATE_KEY={_base64url(private_key_bytes)}')
        self.stdout.write(f'VAPID_SUBJECT={subject}')
