from django.contrib import admin

from .models import Comment, Membership, Organization, Project, Task


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner']
    list_filter = ['owner']


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['organization', 'user', 'role']
    list_filter = ['role', 'organization']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'created_at']
    list_filter = ['organization']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'project', 'status', 'priority', 'assignee', 'created_by']
    list_filter = ['status', 'priority', 'project']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['task', 'author', 'created_at']
    list_filter = ['author', 'created_at']
