from django import template

register = template.Library()

@register.filter
def star_rating(value, max_value=5):
    try:
        value = int(value)  # Ensure the rating is an integer
    except (ValueError, TypeError):
        value = 0
    full_stars = '★' * value
    empty_stars = '☆' * (max_value - value)
    return full_stars + empty_stars


