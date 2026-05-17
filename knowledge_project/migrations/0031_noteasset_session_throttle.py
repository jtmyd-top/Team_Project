import os
import re
from urllib.parse import unquote, urlparse

from django.db import migrations, models
import django.db.models.deletion


def extract_protected_upload_paths(html_content):
    paths = set()
    if not html_content:
        return paths

    for raw_value in re.findall(r'/protected_uploads/[^\s"\'<>]+', str(html_content)):
        parsed = urlparse(raw_value)
        path = unquote(parsed.path or raw_value)
        prefix = '/protected_uploads/'
        if not path.startswith(prefix):
            continue
        file_path = path[len(prefix):].lstrip('/\\')
        normalized = os.path.normpath(file_path).replace('\\', '/')
        if normalized and not normalized.startswith('../') and normalized != '..':
            paths.add(normalized)
    return paths


def backfill_note_asset_links(apps, schema_editor):
    Note = apps.get_model('knowledge_project', 'Note')
    Asset = apps.get_model('knowledge_project', 'Asset')
    NoteAsset = apps.get_model('knowledge_project', 'NoteAsset')

    asset_by_file = {
        asset.file: asset
        for asset in Asset.objects.exclude(file='')
    }
    links = []
    for note in Note.objects.exclude(content__isnull=True).exclude(content='').iterator():
        for path in extract_protected_upload_paths(note.content):
            asset = asset_by_file.get(path)
            if asset is not None:
                links.append(NoteAsset(note_id=note.id, asset_id=asset.id))

    if links:
        NoteAsset.objects.bulk_create(links, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0030_merge_20260517_avatars_http404'),
    ]

    operations = [
        migrations.CreateModel(
            name='NoteAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='note_links', to='knowledge_project.asset')),
                ('note', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asset_links', to='knowledge_project.note')),
            ],
            options={
                'verbose_name': 'Note asset link',
                'verbose_name_plural': 'Note asset links',
                'unique_together': {('note', 'asset')},
            },
        ),
        migrations.AddIndex(
            model_name='noteasset',
            index=models.Index(fields=['asset', 'note'], name='noteasset_asset_note_idx'),
        ),
        migrations.RunPython(backfill_note_asset_links, migrations.RunPython.noop),
    ]
