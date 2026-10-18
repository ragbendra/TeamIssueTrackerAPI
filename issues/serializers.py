from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Comment, Membership, Organization, Project, Task


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
        if self.instance and organization != self.instance.organization:
            raise serializers.ValidationError(
                'A project organization cannot be changed.'
            )
        return organization


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'task', 'author', 'body', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']

    def validate_task(self, task):
        request = self.context.get('request')
        if request and not task.project.organization.memberships.filter(user=request.user).exists():
            raise serializers.ValidationError('You are not a member of this task organization.')
        return task


class TaskSerializer(serializers.ModelSerializer):
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        allow_null=True,
        required=False,
    )
    assignee_detail = UserSummarySerializer(source='assignee', read_only=True)
    created_by = UserSummarySerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
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
            'created_at',
            'comments',
            'initial_comment',
        ]
        read_only_fields = ['id', 'created_by', 'created_at']

    def validate_project(self, project):
        request = self.context.get('request')
        if request and not project.organization.memberships.filter(user=request.user).exists():
            raise serializers.ValidationError('You are not a member of this project organization.')
        return project

    def validate(self, attrs):
        project = attrs.get('project')
        if project is None and self.instance is not None:
            project = self.instance.project
        assignee = attrs.get('assignee')
        if assignee is not None and not Membership.objects.filter(
            organization=project.organization,
            user=assignee,
        ).exists():
            raise serializers.ValidationError({
                'assignee': 'The assignee must be a member of the task organization.'
            })
        return attrs

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
