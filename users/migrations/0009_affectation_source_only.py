# AffectationEntreprise : user_id / client_id → champ unique ``source`` (+ entreprise).

from django.db import migrations, models


def fill_source_from_fks(apps, schema_editor):
    AffectationEntreprise = apps.get_model('users', 'AffectationEntreprise')
    for row in AffectationEntreprise.objects.all().iterator():
        src = row.user_id or row.client_id
        if src:
            AffectationEntreprise.objects.filter(pk=row.pk).update(source=src)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_affectation_entreprise'),
    ]

    operations = [
        migrations.AddField(
            model_name='affectationentreprise',
            name='source',
            field=models.CharField(
                blank=True,
                help_text='Identifiant du compte lié (pk utilisateur staff ou pk client portail).',
                max_length=255,
                null=True,
                verbose_name='source',
            ),
        ),
        migrations.RunPython(fill_source_from_fks, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='affectationentreprise',
            name='affectation_staff_xor_client',
        ),
        migrations.RemoveConstraint(
            model_name='affectationentreprise',
            name='unique_user_entreprise_affectation',
        ),
        migrations.RemoveConstraint(
            model_name='affectationentreprise',
            name='unique_client_entreprise_affectation',
        ),
        migrations.RemoveField(
            model_name='affectationentreprise',
            name='user',
        ),
        migrations.RemoveField(
            model_name='affectationentreprise',
            name='client',
        ),
        migrations.RemoveField(
            model_name='affectationentreprise',
            name='cree_le',
        ),
        migrations.AlterField(
            model_name='affectationentreprise',
            name='source',
            field=models.CharField(
                help_text='Identifiant du compte lié (pk utilisateur staff ou pk client portail).',
                max_length=255,
                verbose_name='source',
            ),
        ),
        migrations.AddConstraint(
            model_name='affectationentreprise',
            constraint=models.UniqueConstraint(
                fields=('source', 'entreprise'),
                name='unique_source_entreprise_affectation',
            ),
        ),
    ]
