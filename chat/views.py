from rest_framework import viewsets, status, generics, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import CustomUser, Group, GroupMember, DirectMessage, GroupMessage
from .serializers import (
    UserSerializer,
    SignUpSerializer,
    GroupSerializer,
    GroupCreateSerializer,
    GroupDetailSerializer,
    DirectMessageSerializer,
    GroupMessageSerializer,
    UserSearchSerializer,
    UserProfileSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom login view returning user data with tokens"""
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            username = request.data.get('username')
            user = User.objects.get(username=username)
            user_serializer = UserSerializer(
                user, context={'request': request})

            response.data['user'] = user_serializer.data

            # Update online status
            try:
                custom_user = user.profile
                custom_user.is_online = True
                custom_user.save()
            except CustomUser.DoesNotExist:
                CustomUser.objects.create(user=user, is_online=True)

        return response


class SignUpView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = SignUpSerializer
    permission_classes = (AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        user_serializer = UserSerializer(user, context={'request': request})

        return Response({
            'user': user_serializer.data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout endpoint - update user online status"""
    try:
        custom_user = request.user.profile
        custom_user.is_online = False
        custom_user.save()
    except CustomUser.DoesNotExist:
        pass

    return Response(
        {'message': 'Logout successful'},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """Get current authenticated user details"""
    serializer = UserSerializer(request.user, context={'request': request})
    return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User operations"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']

    @action(detail=False, methods=['get'])
    def search_users(self, request):
        """Search users by username, email, or name"""
        search_query = request.query_params.get('q', '')

        if not search_query:
            return Response(
                {'message': 'Please provide a search query'},
                status=status.HTTP_400_BAD_REQUEST
            )

        users = User.objects.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        ).exclude(id=request.user.id)[:20]

        serializer = UserSearchSerializer(
            users,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'put'])
    def profile(self, request):
        """Get or update current user profile"""
        if request.method == 'GET':
            serializer = UserSerializer(
                request.user, context={'request': request})
            return Response(serializer.data)

        elif request.method == 'PUT':
            serializer = UserSerializer(
                request.user,
                data=request.data,
                partial=True,
                context={'request': request}
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def upload_profile_image(self, request):
        """Upload profile image"""
        try:
            custom_user = request.user.profile
        except CustomUser.DoesNotExist:
            custom_user = CustomUser.objects.create(user=request.user)

        serializer = UserProfileSerializer(
            custom_user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def update_online_status(self, request):
        """Update user online status"""
        is_online = request.data.get('is_online', False)

        try:
            custom_user = request.user.profile
        except CustomUser.DoesNotExist:
            custom_user = CustomUser.objects.create(user=request.user)

        custom_user.is_online = is_online
        custom_user.save()

        return Response({
            'message': f'User is now {"online" if is_online else "offline"}',
            'is_online': custom_user.is_online
        })


class GroupViewSet(viewsets.ModelViewSet):
    """ViewSet for Group operations"""
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-updated_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return GroupCreateSerializer
        elif self.action == 'retrieve':
            return GroupDetailSerializer
        return GroupSerializer

    def create(self, request, *args, **kwargs):
        """Create a new group"""
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Return full group details
        group_detail = GroupDetailSerializer(
            serializer.instance,
            context={'request': request}
        )
        return Response(group_detail.data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """List all groups where user is a member"""
        groups = self.get_queryset().filter(members=request.user)
        serializer = self.get_serializer(groups, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """Get group details with messages"""
        group = self.get_object()

        # Check if user is member of group
        if not group.members.filter(id=request.user.id).exists():
            return Response(
                {'message': 'You are not a member of this group'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(group)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        """Add a member to group"""
        group = self.get_object()

        # Check if user is group creator
        if group.creator != request.user:
            return Response(
                {'message': 'Only group creator can add members'},
                status=status.HTTP_403_FORBIDDEN
            )

        user_id = request.data.get('user_id')
        user = get_object_or_404(User, id=user_id)

        # Check if user is already a member
        if group.members.filter(id=user.id).exists():
            return Response(
                {'message': 'User is already a member of this group'},
                status=status.HTTP_400_BAD_REQUEST
            )

        GroupMember.objects.create(group=group, user=user)

        serializer = self.get_serializer(group)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        """Remove a member from group"""
        group = self.get_object()

        # Check if user is group creator
        if group.creator != request.user:
            return Response(
                {'message': 'Only group creator can remove members'},
                status=status.HTTP_403_FORBIDDEN
            )

        user_id = request.data.get('user_id')

        try:
            group_member = GroupMember.objects.get(
                group=group, user_id=user_id)
            group_member.delete()

            serializer = self.get_serializer(group)
            return Response(serializer.data)
        except GroupMember.DoesNotExist:
            return Response(
                {'message': 'User is not a member of this group'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def leave_group(self, request, pk=None):
        """Leave a group"""
        group = self.get_object()

        try:
            group_member = GroupMember.objects.get(
                group=group, user=request.user)
            group_member.delete()

            return Response({'message': 'You have left the group'})
        except GroupMember.DoesNotExist:
            return Response(
                {'message': 'You are not a member of this group'},
                status=status.HTTP_400_BAD_REQUEST
            )


class DirectMessageViewSet(viewsets.ModelViewSet):
    """ViewSet for Direct Messages"""
    queryset = DirectMessage.objects.all()
    serializer_class = DirectMessageSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """List all conversations for current user"""
        # Get unique conversations
        conversations = DirectMessage.objects.filter(
            Q(sender=request.user) | Q(receiver=request.user)
        ).values('sender_id', 'receiver_id').distinct()

        result = []
        seen = set()

        for conv in conversations:
            sender_id = conv['sender_id']
            receiver_id = conv['receiver_id']

            # Create a unique identifier for the conversation
            pair = tuple(sorted([sender_id, receiver_id]))

            if pair not in seen:
                seen.add(pair)
                other_user_id = sender_id if receiver_id == request.user.id else receiver_id
                other_user = User.objects.get(id=other_user_id)

                # Get last message
                last_msg = DirectMessage.objects.filter(
                    Q(sender_id=sender_id, receiver_id=receiver_id) |
                    Q(sender_id=receiver_id, receiver_id=sender_id)
                ).latest('created_at')

                result.append({
                    'other_user': UserSerializer(other_user, context={'request': request}).data,
                    'last_message': DirectMessageSerializer(last_msg, context={'request': request}).data,
                })

        return Response(result)

    def create(self, request, *args, **kwargs):
        """Create a new direct message"""
        serializer = self.get_serializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def conversation(self, request):
        """Get messages between two users"""
        other_user_id = request.query_params.get('user_id')

        if not other_user_id:
            return Response(
                {'message': 'user_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        messages = DirectMessage.objects.filter(
            Q(sender=request.user, receiver_id=other_user_id) |
            Q(sender_id=other_user_id, receiver=request.user)
        ).order_by('created_at')

        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)


class GroupMessageViewSet(viewsets.ModelViewSet):
    """ViewSet for Group Messages"""
    queryset = GroupMessage.objects.all()
    serializer_class = GroupMessageSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """Create a new group message"""
        group_id = request.data.get('group')

        # Verify user is member of group
        group = get_object_or_404(Group, id=group_id)
        if not group.members.filter(id=request.user.id).exists():
            return Response(
                {'message': 'You are not a member of this group'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def group_messages(self, request):
        """Get messages for a specific group"""
        group_id = request.query_params.get('group_id')

        if not group_id:
            return Response(
                {'message': 'group_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        group = get_object_or_404(Group, id=group_id)

        # Check if user is member
        if not group.members.filter(id=request.user.id).exists():
            return Response(
                {'message': 'You are not a member of this group'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get last 50 messages for infinite scroll
        messages = group.messages.all().order_by('-created_at')[:50]
        messages = sorted(messages, key=lambda x: x.created_at)

        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)
