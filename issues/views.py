from rest_framework import generics, permissions, viewsets

from .models import Comment, Membership, Organization, Project, Task
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

    def get_queryset(self):
        return Project.objects.filter(
            organization__memberships__user=self.request.user,
        ).distinct()


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.filter(
            project__organization__memberships__user=self.request.user,
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        return Comment.objects.filter(
            task__project__organization__memberships__user=self.request.user,
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
