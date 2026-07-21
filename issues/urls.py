from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import OrganizationViewSet, ProjectViewSet, RegisterView

router = DefaultRouter()
router.register('organizations', OrganizationViewSet, basename='organization')
router.register('projects', ProjectViewSet, basename='project')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]

urlpatterns += router.urls
