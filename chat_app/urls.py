from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from chat.views import (
    CustomTokenObtainPairView,
    SignUpView,
    logout_view,
    get_current_user,
    UserViewSet,
    GroupViewSet,
    DirectMessageViewSet,
    GroupMessageViewSet,
)

# Initialize router
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'direct-messages', DirectMessageViewSet,
                basename='direct-message')
router.register(r'group-messages', GroupMessageViewSet,
                basename='group-message')

# URL patterns
urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Authentication endpoints
    path('api/auth/login/', CustomTokenObtainPairView.as_view(),
         name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/signup/', SignUpView.as_view(), name='signup'),
    path('api/auth/logout/', logout_view, name='logout'),
    path('api/auth/me/', get_current_user, name='current_user'),

    # API routes
    path('api/', include(router.urls)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
