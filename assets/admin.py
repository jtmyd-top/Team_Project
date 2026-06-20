import hashlib
import os

from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from .models import Asset


def calculate_file_hash_for_admin(file):
    hasher = hashlib.sha256()
    for chunk in file.chunks():
        hasher.update(chunk)
    file.seek(0)
    return hasher.hexdigest()


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'asset_type', 'uploader', 'uploaded_at')
    list_filter = ('asset_type', 'uploader')
    search_fields = ('name', 'uploader__username')
    autocomplete_fields = ['uploader']
    readonly_fields = ('uploaded_at', 'image_hash')

    def get_fields(self, request, obj=None):
        if obj is None:
            return ('uploader', 'file', 'asset_type', 'description')
        return ('name', 'uploader', 'file', 'asset_type', 'description', 'uploaded_at', 'image_hash')

    def get_readonly_fields(self, request, obj=None):
        base_readonly = list(self.readonly_fields)
        if obj:
            base_readonly.append('name')
        return tuple(base_readonly)

    def save_model(self, request, obj, form, change):
        if not obj.uploader_id:
            obj.uploader = request.user

        uploaded_file = form.cleaned_data.get('file')
        if uploaded_file and 'file' in form.changed_data:
            file_hash = calculate_file_hash_for_admin(uploaded_file)
            existing_asset = Asset.objects.filter(
                uploader=obj.uploader,
                image_hash=file_hash,
            ).exclude(pk=obj.pk).first()

            if existing_asset:
                obj.pk = None
                existing_asset_url = reverse('admin:notes_asset_change', args=[existing_asset.pk])
                messages.set_level(request, messages.ERROR)
                messages.error(
                    request,
                    format_html(
                        '上传失败：您已上传过相同内容的文件。请访问 <a href="{}">这里</a> 查看已存在的资产。',
                        existing_asset_url,
                    ),
                )
                return
            obj.image_hash = file_hash

        super().save_model(request, obj, form, change)

        if not obj.name and obj.file:
            obj.name = os.path.basename(obj.file.name)
            obj.save(update_fields=['name'])
