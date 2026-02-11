from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CustomUser(models.Model):
    """Extended User Model for profile image"""
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile')
    profile_image = models.ImageField(
        upload_to='profile_images/',
        null=True,
        blank=True,
        max_length=255
    )
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'custom_user'
        verbose_name = 'Custom User'
        verbose_name_plural = 'Custom Users'

    def __str__(self):
        return f"{self.user.username} Profile"


class Group(models.Model):
    """Group Model for group chats"""
    name = models.CharField(max_length=255)
    creator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_groups')
    members = models.ManyToManyField(
        User, through='GroupMember', related_name='chat_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'group'
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class GroupMember(models.Model):
    """Through model for Group and User relationship"""
    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name='group_members')
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='group_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_member'
        unique_together = ('group', 'user')
        verbose_name = 'Group Member'
        verbose_name_plural = 'Group Members'

    def __str__(self):
        return f"{self.user.username} in {self.group.name}"


class DirectMessage(models.Model):
    """Direct Message Model for one-on-one chats"""
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = 'direct_message'
        verbose_name = 'Direct Message'
        verbose_name_plural = 'Direct Messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['sender', 'receiver', 'created_at']),
        ]

    def __str__(self):
        return f"Message from {self.sender.username} to {self.receiver.username}"


class GroupMessage(models.Model):
    """Group Message Model for group chats"""
    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='group_messages')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_message'
        verbose_name = 'Group Message'
        verbose_name_plural = 'Group Messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['group', 'created_at']),
        ]

    def __str__(self):
        return f"Message in {self.group.name} by {self.sender.username}"
