from rest_framework import permissions

from .models import Comment, Membership, Organization, Project, Task


def get_organization(obj):
    if isinstance(obj, Organization):
        return obj
    if isinstance(obj, Project):
        return obj.organization
    if isinstance(obj, Task):
        return obj.project.organization
    if isinstance(obj, Comment):
        return obj.task.project.organization
    return None


def get_membership(user, organization):
    if not user or not user.is_authenticated or organization is None:
        return None
    return Membership.objects.filter(
        user=user,
        organization=organization,
    ).first()


class IsOrgMember(permissions.BasePermission):
    """Allow access to objects belonging to an organization the user joined."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return get_membership(request.user, get_organization(obj)) is not None


class IsOrganizationMemberOrAdmin(permissions.BasePermission):
    """Members can read organizations; admins and owners can update them."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        membership = get_membership(request.user, get_organization(obj))
        if membership is None:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method == 'DELETE':
            return membership.role == Membership.Role.OWNER
        return membership.role in {
            Membership.Role.ADMIN,
            Membership.Role.OWNER,
        }


class IsOrgAdminOrOwner(IsOrgMember):
    """Members can read projects; only organization admins or owners can change them."""

    def has_object_permission(self, request, view, obj):
        membership = get_membership(request.user, get_organization(obj))
        if membership is None:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return membership.role in {
            Membership.Role.ADMIN,
            Membership.Role.OWNER,
        }


class IsCommentAuthorOrOrgAdmin(IsOrgMember):
    """Members can read/create comments; authors and org admins can delete."""

    def has_object_permission(self, request, view, obj):
        membership = get_membership(request.user, get_organization(obj))
        if membership is None:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method == 'DELETE':
            return (
                obj.author_id == request.user.id
                or membership.role in {
                    Membership.Role.ADMIN,
                    Membership.Role.OWNER,
                }
            )
        return False


class IsAssigneeOrCreatorOrAdmin(IsOrgMember):
    """Members can read tasks; task owners or organization admins can change them."""

    def has_object_permission(self, request, view, obj):
        membership = get_membership(request.user, get_organization(obj))
        if membership is None:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            membership.role in {Membership.Role.ADMIN, Membership.Role.OWNER}
            or obj.assignee_id == request.user.id
            or obj.created_by_id == request.user.id
        )
