
import django.db.models.deletion
import django.utils.timezone
import ninja_aio.models.serializers
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(max_length=50)),
                ('ref', models.PositiveIntegerField()),
            ],
            options={
                'ordering': ['pk'],
            },
        ),
        migrations.CreateModel(
            name='Author',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('bio', models.TextField(blank=True, default='')),
                ('birth_date', models.DateField(blank=True, null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ninja_aio.models.serializers.BaseSerializer),
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Book',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('isbn', models.CharField(max_length=13, unique=True)),
                ('pages', models.PositiveIntegerField(default=0)),
                ('published', models.DateField(blank=True, null=True)),
                ('available', models.BooleanField(default=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='books', to='library.author')),
                ('tags', models.ManyToManyField(blank=True, related_name='books', to='library.tag')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ninja_aio.models.serializers.BaseSerializer),
        ),
        migrations.CreateModel(
            name='Member',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('role', models.CharField(choices=[('librarian', 'Librarian'), ('member', 'Member')], default='member', max_length=20)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='member', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ninja_aio.models.serializers.BaseSerializer),
        ),
        migrations.CreateModel(
            name='Loan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('borrowed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('due_date', models.DateField()),
                ('returned_at', models.DateTimeField(blank=True, null=True)),
                ('renewals', models.PositiveSmallIntegerField(default=0)),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='loans', to='library.book')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='loans', to='library.member')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, ninja_aio.models.serializers.BaseSerializer),
        ),
    ]
