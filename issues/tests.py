from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Comment, Membership, Organization, Project, Task


class IssueTrackerAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            password='owner-password-123',
        )
        self.member = User.objects.create_user(
            username='member',
            password='member-password-123',
        )
        self.organization = Organization.objects.create(
            name='Acme Engineering',
            owner=self.owner,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=Membership.Role.OWNER,
        )
        Membership.objects.create(
            organization=self.organization,
            user=self.member,
            role=Membership.Role.MEMBER,
        )
        self.project = Project.objects.create(
            organization=self.organization,
            name='Backend API',
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def create_task(self, **overrides):
        values = {
            'project': self.project,
            'title': 'Fix endpoint',
            'description': 'Improve the API response.',
            'status': Task.Status.TODO,
            'priority': Task.Priority.MED,
            'created_by': self.owner,
        }
        values.update(overrides)
        return Task.objects.create(**values)

    def test_register_and_login(self):
        register_response = self.client.post(
            reverse('auth-register'),
            {'username': 'new-user', 'password': 'new-password-123'},
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        token_response = self.client.post(
            reverse('token-obtain-pair'),
            {'username': 'new-user', 'password': 'new-password-123'},
        )
        self.assertEqual(token_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', token_response.data)
        self.assertIn('refresh', token_response.data)

    def test_organization_creation_adds_owner_membership(self):
        self.authenticate(self.owner)
        response = self.client.post(
            reverse('organization-list'),
            {'name': 'New Organization'},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        organization = Organization.objects.get(id=response.data['id'])
        membership = Membership.objects.get(
            organization=organization,
            user=self.owner,
        )
        self.assertEqual(membership.role, Membership.Role.OWNER)

    def test_member_can_view_project(self):
        self.authenticate(self.member)
        response = self.client.get(
            reverse('project-detail', kwargs={'pk': self.project.id}),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_member_cannot_modify_project(self):
        self.authenticate(self.member)
        response = self.client.patch(
            reverse('project-detail', kwargs={'pk': self.project.id}),
            {'name': 'Unauthorized rename'},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_task_creation_with_initial_comment(self):
        self.authenticate(self.owner)
        response = self.client.post(
            reverse('task-list'),
            {
                'project': self.project.id,
                'title': 'Add initial comment support',
                'initial_comment': 'This should create both records.',
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(id=response.data['id'])
        comment = Comment.objects.get(task=task)
        self.assertEqual(comment.body, 'This should create both records.')
        self.assertEqual(response.data['comments'][0]['body'], comment.body)

    def test_task_creator_can_close_task(self):
        task = self.create_task()
        self.authenticate(self.owner)
        response = self.client.post(
            reverse('task-close', kwargs={'pk': task.id}),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Task.Status.DONE)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)

    def test_unrelated_member_cannot_close_task(self):
        task = self.create_task()
        self.authenticate(self.member)
        response = self.client.post(
            reverse('task-close', kwargs={'pk': task.id}),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assignee_can_close_task(self):
        task = self.create_task(assignee=self.member)
        self.authenticate(self.member)
        response = self.client.post(
            reverse('task-close', kwargs={'pk': task.id}),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)

    def test_tasks_can_be_filtered(self):
        self.create_task(title='Todo high', priority=Task.Priority.HIGH)
        self.create_task(
            title='In progress low',
            status=Task.Status.IN_PROGRESS,
            priority=Task.Priority.LOW,
        )
        self.authenticate(self.owner)
        response = self.client.get(
            reverse('task-list'),
            {'status': Task.Status.TODO, 'priority': Task.Priority.HIGH},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Todo high')

    def test_tasks_are_paginated_and_orderable(self):
        self.create_task(title='First task')
        self.create_task(title='Second task')
        self.authenticate(self.owner)
        response = self.client.get(
            reverse('task-list'),
            {'page_size': 1, 'ordering': 'priority'},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 1)
