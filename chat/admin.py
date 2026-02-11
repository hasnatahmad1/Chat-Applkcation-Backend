from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, Group, GroupMember, DirectMessage, GroupMessage


class CustomUserInline(admin.StackedInline):
    """Inline admin for CustomUser"""
    model = CustomUser
    can_delete = False
    fields = ['profile_image', 'is_online', 'last_seen']


class CustomUserAdmin(BaseUserAdmin):
    """Extended User Admin with profile fields"""
    inlines = (CustomUserInline,)


class GroupMemberInline(admin.TabularInline):
    """Inline admin for GroupMembers"""
    model = GroupMember
    extra = 1
    fields = ['user', 'joined_at']
    readonly_fields = ['joined_at']


@admin.register(CustomUser)
class CustomUserModelAdmin(admin.ModelAdmin):
    """Admin for CustomUser model"""
    list_display = ['id', 'user', 'is_online', 'last_seen']
    list_filter = ['is_online', 'last_seen']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['last_seen']

    fieldsets = (
        ('User Info', {'fields': ('user',)}),
        ('Profile', {'fields': ('profile_image',)}),
        ('Status', {'fields': ('is_online', 'last_seen')}),
    )


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """Admin for Group model"""
    list_display = ['id', 'name', 'creator', 'member_count', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'creator__username']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [GroupMemberInline]

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'

    fieldsets = (
        ('Group Info', {'fields': ('name', 'creator')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    """Admin for GroupMember model"""
    list_display = ['id', 'user', 'group', 'joined_at']
    list_filter = ['group', 'joined_at']
    search_fields = ['user__username', 'group__name']
    readonly_fields = ['joined_at']

    fieldsets = (
        ('Membership', {'fields': ('group', 'user')}),
        ('Info', {'fields': ('joined_at',)}),
    )


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    """Admin for DirectMessage model"""
    list_display = ['id', 'sender', 'receiver',
                    'message_preview', 'created_at', 'is_read']
    list_filter = ['created_at', 'is_read']
    search_fields = ['sender__username', 'receiver__username', 'message']
    readonly_fields = ['created_at']

    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'

    fieldsets = (
        ('Participants', {'fields': ('sender', 'receiver')}),
        ('Message', {'fields': ('message',)}),
        ('Status', {'fields': ('is_read', 'created_at')}),
    )


@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    """Admin for GroupMessage model"""
    list_display = ['id', 'group', 'sender', 'message_preview', 'created_at']
    list_filter = ['group', 'created_at']
    search_fields = ['sender__username', 'group__name', 'message']
    readonly_fields = ['created_at']

    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'

    fieldsets = (
        ('Message Info', {'fields': ('group', 'sender')}),
        ('Content', {'fields': ('message',)}),
        ('Timestamp', {'fields': ('created_at',)}),
    )


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
