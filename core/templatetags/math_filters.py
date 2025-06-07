from django import template
register = template.Library()

@register.filter
def div(value, arg):
    try:
        return float(value) / int(arg)
    except:
        return 0
