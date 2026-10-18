import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Comment, Membership, Organization, Project, Task


class IssueTrackerAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='owner-password-123')
        self.member = User.objects.create_user('member', password='member-password-123')
        self.organization = Organization.objects.create(name='Acme Engineering', owner=self.owner)
        Membership.objects.create(organization=self.organization, user=self.owner, role=Membership.Role.OWNER)
        Membership.objects.create(organization=self.organization, user=self.member, role=Membership.Role.MEMBER)
        self.project = Project.objects.create(organization=self.organization, name='Backend API')

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
        register_response = self.client.post(reverse('auth-register'), {'username': 'new-user', 'password': 'new-password-123'})
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        token_response = self.client.post(reverse('token-obtain-pair'), {'username': 'new-user', 'password': 'new-password-123'})
        self.assertEqual(token_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', token_response.data)
        self.assertIn('refresh', token_response.data)

    def test_organization_creation_adds_owner_membership(self):
        self.authenticate(self.owner)
        response = self.client.post(reverse('organization-list'), {'name': 'New Organization'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        organization = Organization.objects.get(id=response.data['id'])
        membership = Membership.objects.get(organization=organization, user=self.owner)
        self.assertEqual(membership.role, Membership.Role.OWNER)

    def test_member_can_view_project(self):
        self.authenticate(self.member)
        response = self.client.get(reverse('project-detail', kwargs={'pk': self.project.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_member_cannot_modify_project(self):
        self.authenticate(self.member)
        response = self.client.patch(reverse('project-detail', kwargs={'pk': self.project.id}), {'name': 'Unauthorized rename'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_task_creation_with_initial_comment(self):
        self.authenticate(self.owner)
        response = self.client.post(reverse('task-list'), {'project': self.project.id, 'title': 'Add initial comment support', 'initial_comment': 'This should create both records.'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(id=response.data['id'])
        comment = Comment.objects.get(task=task)
        self.assertEqual(comment.body, 'This should create both records.')
        self.assertEqual(response.data['comments'][0]['body'], comment.body)

    def test_task_creator_can_close_task(self):
        task = self.create_task()
        self.authenticate(self.owner)
        response = self.client.post(reverse('task-close', kwargs={'pk': task.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Task.Status.DONE)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)

    def test_unrelated_member_cannot_close_task(self):
        task = self.create_task()
        self.authenticate(self.member)
        response = self.client.post(reverse('task-close', kwargs={'pk': task.id}))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assignee_can_close_task(self):
        task = self.create_task(assignee=self.member)
        self.authenticate(self.member)
        response = self.client.post(reverse('task-close', kwargs={'pk': task.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)

    def test_tasks_can_be_filtered(self):
        self.create_task(title='Todo high', priority=Task.Priority.HIGH)
        self.create_task(title='In progress low', status=Task.Status.IN_PROGRESS, priority=Task.Priority.LOW)
        self.authenticate(self.owner)
        response = self.client.get(reverse('task-list'), {'status': Task.Status.TODO, 'priority': Task.Priority.HIGH})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Todo high')

    def test_tasks_are_paginated_and_orderable(self):
        self.create_task(title='First task')
        self.create_task(title='Second task')
        self.authenticate(self.owner)
        response = self.client.get(reverse('task-list'), {'page_size': 1, 'ordering': 'priority'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 1)


class PermissionAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='password-123')
        self.admin = User.objects.create_user('admin', password='password-123')
        self.member = User.objects.create_user('member', password='password-123')
        self.organization = Organization.objects.create(name='Acme Engineering', owner=self.owner)
        for user, role in [(self.owner, Membership.Role.OWNER), (self.admin, Membership.Role.ADMIN), (self.member, Membership.Role.MEMBER)]:
            Membership.objects.create(organization=self.organization, user=user, role=role)
        self.project = Project.objects.create(organization=self.organization, name='Backend API')
        self.task = Task.objects.create(project=self.project, title='Fix endpoint', created_by=self.owner)
        self.comment = Comment.objects.create(task=self.task, author=self.owner, body='Review this.')

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_member_cannot_create_project(self):
        self.authenticate(self.member)
        response = self.client.post(reverse('project-list'), {'organization': self.organization.id, 'name': 'Blocked'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_cannot_patch_organization(self):
        self.authenticate(self.member)
        response = self.client.patch(reverse('organization-detail', kwargs={'pk': self.organization.id}), {'name': 'Blocked'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_patch_organization(self):
        self.authenticate(self.admin)
        response = self.client.patch(reverse('organization-detail', kwargs={'pk': self.organization.id}), {'name': 'Renamed'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_cannot_delete_organization(self):
        self.authenticate(self.admin)
        response = self.client.delete(reverse('organization-detail', kwargs={'pk': self.organization.id}))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_delete_organization_and_projects_are_gone(self):
        self.authenticate(self.owner)
        response = self.client.delete(reverse('organization-detail', kwargs={'pk': self.organization.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(id=self.project.id).exists())

    def test_member_cannot_delete_another_users_comment(self):
        self.authenticate(self.member)
        response = self.client.delete(reverse('comment-detail', kwargs={'pk': self.comment.id}))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_comment_author_can_delete_own_comment(self):
        self.authenticate(self.owner)
        response = self.client.delete(reverse('comment-detail', kwargs={'pk': self.comment.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_can_delete_anyones_comment(self):
        self.authenticate(self.admin)
        response = self.client.delete(reverse('comment-detail', kwargs={'pk': self.comment.id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_can_create_update_delete_projects(self):
        self.authenticate(self.admin)
        create_response = self.client.post(reverse('project-list'), {'organization': self.organization.id, 'name': 'Admin Project'})
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        project_id = create_response.data['id']
        update_response = self.client.patch(reverse('project-detail', kwargs={'pk': project_id}), {'name': 'Updated Admin Project'})
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        delete_response = self.client.delete(reverse('project-detail', kwargs={'pk': project_id}))
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_project_organization_change_is_rejected(self):
        other_org = Organization.objects.create(name='Other', owner=self.owner)
        Membership.objects.create(organization=other_org, user=self.owner, role=Membership.Role.OWNER)
        self.authenticate(self.owner)
        response = self.client.patch(reverse('project-detail', kwargs={'pk': self.project.id}), {'organization': other_org.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuthenticationAndIsolationAPITests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user('user-a', password='password-123')
        self.user_b = User.objects.create_user('user-b', password='password-123')
        self.org_a = Organization.objects.create(name='Org A', owner=self.user_a)
        self.org_b = Organization.objects.create(name='Org B', owner=self.user_b)
        Membership.objects.create(organization=self.org_a, user=self.user_a, role=Membership.Role.OWNER)
        Membership.objects.create(organization=self.org_b, user=self.user_b, role=Membership.Role.OWNER)
        self.project_a = Project.objects.create(organization=self.org_a, name='Project A')
        self.task_a = Task.objects.create(project=self.project_a, title='Task A', created_by=self.user_a)
        self.comment_a = Comment.objects.create(task=self.task_a, author=self.user_a, body='Comment A')

    def token_for(self, username, password='password-123'):
        response = self.client.post(reverse('token-obtain-pair'), {'username': username, 'password': password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def authenticate_with_token(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def test_jwt_end_to_end_workflow(self):
        register = self.client.post(reverse('auth-register'), {'username': 'workflow-user', 'password': 'password-123'})
        self.assertEqual(register.status_code, status.HTTP_201_CREATED)
        tokens = self.token_for('workflow-user')
        self.authenticate_with_token(tokens['access'])
        org_response = self.client.post(reverse('organization-list'), {'name': 'Workflow Org'})
        self.assertEqual(org_response.status_code, status.HTTP_201_CREATED)
        project_response = self.client.post(reverse('project-list'), {'organization': org_response.data['id'], 'name': 'Workflow Project'})
        self.assertEqual(project_response.status_code, status.HTTP_201_CREATED)
        task_response = self.client.post(reverse('task-list'), {'project': project_response.data['id'], 'title': 'Workflow Task', 'initial_comment': 'Created with the task.'})
        self.assertEqual(task_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(task_response.data['comments']), 1)
        comment_response = self.client.post(reverse('comment-list'), {'task': task_response.data['id'], 'body': 'Follow-up comment.'})
        self.assertEqual(comment_response.status_code, status.HTTP_201_CREATED)
        close_response = self.client.post(reverse('task-close', kwargs={'pk': task_response.data['id']}))
        self.assertEqual(close_response.status_code, status.HTTP_200_OK)
        self.assertEqual(close_response.data['status'], Task.Status.DONE)

    def test_token_refresh_returns_new_access_token(self):
        tokens = self.token_for('user-a')
        response = self.client.post(reverse('token-refresh'), {'refresh': tokens['refresh']})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_request_without_token_returns_401(self):
        response = self.client.get(reverse('organization-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_request_with_garbage_token_returns_401(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer garbage-token')
        response = self.client.get(reverse('organization-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_organization_objects_are_isolated(self):
        self.client.force_authenticate(user=self.user_b)
        for name, kwargs in [('organization-detail', {'pk': self.org_a.id}), ('project-detail', {'pk': self.project_a.id}), ('task-detail', {'pk': self.task_a.id}), ('comment-detail', {'pk': self.comment_a.id})]:
            response = self.client.get(reverse(name, kwargs=kwargs))
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        for name in ['organization-list', 'project-list', 'task-list', 'comment-list']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            objects = response.data.get('results', response.data)
            if name == 'organization-list':
                self.assertNotIn(self.org_a.id, [item['id'] for item in objects])
            else:
                self.assertEqual(objects, [])

    def test_cross_organization_task_and_comment_writes_are_rejected(self):
        self.client.force_authenticate(user=self.user_b)
        task_response = self.client.post(reverse('task-list'), {'project': self.project_a.id, 'title': 'Nope'})
        self.assertIn(task_response.status_code, {status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND})
        comment_response = self.client.post(reverse('comment-list'), {'task': self.task_a.id, 'body': 'Nope'})
        self.assertIn(comment_response.status_code, {status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND})


class ValidationAndPaginationAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='password-123')
        self.outsider = User.objects.create_user('outsider', password='password-123')
        self.organization = Organization.objects.create(name='Org', owner=self.owner)
        Membership.objects.create(organization=self.organization, user=self.owner, role=Membership.Role.OWNER)
        self.project = Project.objects.create(organization=self.organization, name='Project')

    def authenticate(self):
        self.client.force_authenticate(user=self.owner)

    def task_payload(self, assignee):
        return {'project': self.project.id, 'title': 'Assigned task', 'assignee': assignee}

    def test_assignee_outside_organization_rejected_on_create_and_update(self):
        self.authenticate()
        create_response = self.client.post(reverse('task-list'), self.task_payload(self.outsider.id))
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        task = Task.objects.create(project=self.project, title='Existing', created_by=self.owner)
        update_response = self.client.patch(reverse('task-detail', kwargs={'pk': task.id}), {'assignee': self.outsider.id})
        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_member_assignee_and_null_assignee_are_accepted(self):
        member = User.objects.create_user('member', password='password-123')
        Membership.objects.create(organization=self.organization, user=member, role=Membership.Role.MEMBER)
        self.authenticate()
        member_response = self.client.post(reverse('task-list'), self.task_payload(member.id))
        self.assertEqual(member_response.status_code, status.HTTP_201_CREATED)
        null_response = self.client.post(reverse('task-list'), self.task_payload(None), format='json')
        self.assertEqual(null_response.status_code, status.HTTP_201_CREATED)

    def test_tasks_filter_by_assignee(self):
        member = User.objects.create_user('member', password='password-123')
        Membership.objects.create(organization=self.organization, user=member, role=Membership.Role.MEMBER)
        Task.objects.create(project=self.project, title='Assigned', assignee=member, created_by=self.owner)
        Task.objects.create(project=self.project, title='Unassigned', created_by=self.owner)
        self.authenticate()
        response = self.client.get(reverse('task-list'), {'assignee': member.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], 'Assigned')

    def test_tasks_default_page_size_is_ten(self):
        for number in range(11):
            Task.objects.create(project=self.project, title=f'Task {number}', created_by=self.owner)
        self.authenticate()
        response = self.client.get(reverse('task-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(len(response.data['results']), 10)

    def test_tasks_page_size_is_capped_at_one_hundred(self):
        for number in range(101):
            Task.objects.create(project=self.project, title=f'Task {number}', created_by=self.owner)
        self.authenticate()
        response = self.client.get(reverse('task-list'), {'page_size': 1000})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 101)
        self.assertEqual(len(response.data['results']), 100)


class SettingsTests(APITestCase):
    def test_debug_false_without_secret_key_raises_improperly_configured(self):
        repo_root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as temp_dir:
            environment = os.environ.copy()
            environment.pop('SECRET_KEY', None)
            environment['DEBUG'] = 'False'
            environment['PYTHONPATH'] = str(repo_root)
            result = subprocess.run([sys.executable, '-c', 'import core.settings'], cwd=temp_dir, env=environment, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SECRET_KEY must be set when DEBUG is False.', result.stderr)
