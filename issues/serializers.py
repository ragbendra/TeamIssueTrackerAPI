from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Comment, Organization, Project, Task


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'password']
        read_only_fields = ['id']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class OrganizationSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Organization
        fields = ['id', 'name', 'owner']
        read_only_fields = ['id', 'owner']


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'organization', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_organization(self, organization):
        request = self.context.get('request')
        if request and not organization.memberships.filter(user=request.user).exists():
            raise serializers.ValidationError('You are not a member of this organization.')
        return organization


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class TaskSerializer(serializers.ModelSerializer):
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        allow_null=True,
        required=False,
    )
    assignee_detail = UserSummarySerializer(source='assignee', read_only=True)
    created_by = UserSummarySerializer(read_only=True)
    initial_comment = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = Task
        fields = [
            'id',
            'project',
            'title',
            'description',
            'status',
            'priority',
            'assignee',
            'assignee_detail',
            'created_by',
            'initial_comment',
        ]
        read_only_fields = ['id', 'created_by']

    def validate_project(self, project):
        request = self.context.get('request')
        if request and not project.organization.memberships.filter(user=request.user).exists():
            raise serializers.ValidationError('You are not a member of this project organization.')
        return project

    def create(self, validated_data):
        initial_comment = validated_data.pop('initial_comment', '').strip()
        task = Task.objects.create(**validated_data)

        if initial_comment:
            Comment.objects.create(
                task=task,
                author=task.created_by,
                body=initial_comment,
            )

        return task
