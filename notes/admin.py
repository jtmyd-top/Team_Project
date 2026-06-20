from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django_ckeditor_5.widgets import CKEditor5Widget

from .models import Note, Tag


class NoteAdminForm(forms.ModelForm):
    content = forms.CharField(
        label="笔记内容",
        widget=CKEditor5Widget(config_name='full'),
        required=False,
    )

    class Meta:
        model = Note
        fields = '__all__'


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    form = NoteAdminForm
    list_display = ('title', 'author', 'is_public', 'is_secret', 'display_public_link', 'created_at')
    list_filter = ('is_public', 'is_secret', 'author')
    search_fields = ('title', 'author__username', 'content')
    autocomplete_fields = ['author']
    readonly_fields = ('public_id',)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.is_secret:
            readonly.extend(['title', 'content', 'is_secret'])
        return readonly

    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        else:
            obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description='公开链接')
    def display_public_link(self, obj):
        if obj.is_public:
            try:
                url = reverse('public_note_view', args=[obj.public_id])
                return format_html('<a href="{}" target="_blank">点击查看</a>', url)
            except Exception:
                return "链接未配置"
        return "未公开"


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
