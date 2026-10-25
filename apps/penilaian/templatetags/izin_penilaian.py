from django import template

from .. import permissions

register = template.Library()


@register.filter
def bisa_kelola_periode(user):
    return permissions.bisa_kelola_periode(user)
