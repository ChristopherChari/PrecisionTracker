from django import template

register = template.Library()

@register.filter(name='replace')
def replace(value, arg):
    """
    Custom Django filter to replace part of a string.
    Use: {{ value|replace:"old,new" }}
    """
    old_value, new_value = arg.split(',')
    return value.replace(old_value, new_value)
