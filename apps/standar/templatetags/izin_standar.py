from django import template

from .. import permissions

register = template.Library()


@register.filter
def bisa_impor_standar(user):
    return permissions.bisa_impor_standar(user)
