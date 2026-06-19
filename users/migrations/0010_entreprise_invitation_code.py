import secrets

from django.db import migrations, models


ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def populate_invitation_codes(apps, schema_editor):
    Entreprise = apps.get_model('users', 'Entreprise')
    used = set(
        Entreprise.objects.exclude(invitation_code__isnull=True)
        .exclude(invitation_code='')
        .values_list('invitation_code', flat=True)
    )
    for entreprise in Entreprise.objects.all().order_by('pk'):
        while True:
            code = 'ENT-' + ''.join(secrets.choice(ALPHABET) for _ in range(6))
            if code not in used:
                break
        used.add(code)
        entreprise.invitation_code = code
        entreprise.save(update_fields=['invitation_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_affectation_source_only'),
    ]

    operations = [
        migrations.AddField(
            model_name='entreprise',
            name='invitation_code',
            field=models.CharField(blank=True, db_index=True, max_length=16, null=True),
        ),
        migrations.RunPython(populate_invitation_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='entreprise',
            name='invitation_code',
            field=models.CharField(db_index=True, editable=False, max_length=16, unique=True),
        ),
    ]
