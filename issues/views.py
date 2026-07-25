from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from .models import Comment, Membership, Organization, Project, Task
from .permissions import IsAssigneeOrCreatorOrAdmin, IsOrgAdminOrOwner
from .serializers import (
    CommentSerializer,
    OrganizationSerializer,
    ProjectSerializer,
    RegisterSerializer,
    TaskSerializer,
)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        return Organization.objects.filter(
            memberships__user=self.request.user,
        ).distinct()

    def perform_create(self, serializer):
        organization = serializer.save(owner=self.request.user)
        Membership.objects.create(
            organization=organization,
            user=self.request.user,
            role=Membership.Role.OWNER,
        )


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsOrgAdminOrOwner]

    def get_queryset(self):
        return Project.objects.filter(
            organization__memberships__user=self.request.user,
        ).distinct()

    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        project = self.get_object()
        serializer = TaskSerializer(
            project.tasks.all(),
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAssigneeOrCreatorOrAdmin]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'priority', 'assignee']
    ordering_fields = ['created_at', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        return Task.objects.filter(
            project__organization__memberships__user=self.request.user,
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        task = self.get_object()
        task.status = Task.Status.DONE
        task.save(update_fields=['status'])
        return Response(self.get_serializer(task).data, status=status.HTTP_200_OK)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        return Comment.objects.filter(
            task__project__organization__memberships__user=self.request.user,
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
