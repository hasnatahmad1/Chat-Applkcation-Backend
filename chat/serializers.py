from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.files.uploadedfile import InMemoryUploadedFile
from .models import CustomUser, Group, GroupMember, DirectMessage, GroupMessage
import os


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for User Profile with profile image"""
    profile_image = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()
    last_seen = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'profile_image', 'is_online', 'last_seen']

    def get_profile_image(self, obj):
        request = self.context.get('request')
        if obj.profile_image:
            if request is not None:
                return request.build_absolute_uri(obj.profile_image.url)
            return obj.profile_image.url
        return None

    def get_is_online(self, obj):
        return obj.is_online

    def get_last_seen(self, obj):
        return obj.last_seen


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User with profile details"""
    profile = UserProfileSerializer(read_only=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email',
                  'first_name', 'last_name', 'profile']


class SignUpSerializer(serializers.ModelSerializer):
    """Serializer for User Registration"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        label='Confirm Password'
    )
    profile_image = serializers.ImageField(required=False, allow_null=True)
    first_name = serializers.CharField(required=True, max_length=30)
    last_name = serializers.CharField(required=True, max_length=30)

    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name',
                  'password', 'password2', 'profile_image']

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password2'):
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def create(self, validated_data):
        profile_image = validated_data.pop('profile_image', None)

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
        )

        # Create CustomUser profile
        custom_user = CustomUser.objects.create(user=user)

        if profile_image:
            custom_user.profile_image = profile_image
            custom_user.save()

        return user


class GroupMemberSerializer(serializers.ModelSerializer):
    """Serializer for Group Members"""
    user = UserSerializer(read_only=True)

    class Meta:
        model = GroupMember
        fields = ['id', 'user', 'joined_at']


class DirectMessageSerializer(serializers.ModelSerializer):
    """Serializer for Direct Messages"""
    sender = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)
    sender_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        source='sender'
    )
    receiver_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        source='receiver'
    )

    class Meta:
        model = DirectMessage
        fields = ['id', 'sender', 'sender_id', 'receiver',
                  'receiver_id', 'message', 'created_at', 'is_read']
        read_only_fields = ['created_at']

    def create(self, validated_data):
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)


class GroupMessageSerializer(serializers.ModelSerializer):
    """Serializer for Group Messages"""
    sender = UserSerializer(read_only=True)
    sender_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True,
        source='sender'
    )

    class Meta:
        model = GroupMessage
        fields = ['id', 'group', 'sender',
                  'sender_id', 'message', 'created_at']
        read_only_fields = ['created_at']

    def create(self, validated_data):
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Groups with basic info"""
    creator = UserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()
    members = GroupMemberSerializer(
        source='group_members', many=True, read_only=True)

    class Meta:
        model = Group
        fields = ['id', 'name', 'creator', 'members',
                  'member_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def get_member_count(self, obj):
        return obj.members.count()


class GroupCreateSerializer(serializers.ModelSerializer):
    """Serializer for Creating Groups"""
    member_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        write_only=True,
        source='members'
    )

    class Meta:
        model = Group
        fields = ['id', 'name', 'member_ids']

    def validate_member_ids(self, value):
        if len(value) < 2:
            raise serializers.ValidationError(
                "Group must have at least 2 members."
            )
        return value

    def create(self, validated_data):
        members = validated_data.pop('members')
        user = self.context['request'].user

        # Ensure creator is included in members
        if user not in members:
            members = list(members) + [user]

        group = Group.objects.create(
            name=validated_data['name'],
            creator=user
        )

        # Add members to group
        for member in members:
            GroupMember.objects.create(group=group, user=member)

        return group


class GroupDetailSerializer(serializers.ModelSerializer):
    """Detailed Serializer for Group with messages"""
    creator = UserSerializer(read_only=True)
    members = GroupMemberSerializer(
        source='group_members', many=True, read_only=True)
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'creator', 'members',
                  'messages', 'created_at', 'updated_at']

    def get_messages(self, obj):
        # Get last 50 messages for infinite scroll
        messages = obj.messages.all().order_by('-created_at')[:50]
        messages = sorted(messages, key=lambda x: x.created_at)
        return GroupMessageSerializer(messages, many=True, context=self.context).data


class UserSearchSerializer(serializers.ModelSerializer):
    """Serializer for searching users"""
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email',
                  'first_name', 'last_name', 'profile']
