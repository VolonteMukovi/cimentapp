from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('users', '0009_affectation_source_only'),
    ]

    operations = [
        migrations.CreateModel(
            name='Fournisseur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=150)),
                ('contact', models.CharField(max_length=150)),
                (
                    'statut',
                    models.CharField(
                        choices=[('actif', 'Actif'), ('inactif', 'Inactif')], default='actif', max_length=10
                    ),
                ),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                (
                    'entreprise',
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='fournisseurs', to='users.entreprise'),
                ),
            ],
            options={
                'verbose_name': 'fournisseur',
                'verbose_name_plural': 'fournisseurs',
                'ordering': ['-date_creation'],
            },
        ),
    ]

