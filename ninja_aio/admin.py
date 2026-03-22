from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist
from django.db.models import ManyToManyField

from ninja_aio.types import ModelSerializerMeta

TEXT_FIELDS = frozenset({
    "CharField", "TextField", "SlugField", "EmailField", "URLField",
})
FILTER_FIELDS = frozenset({
    "BooleanField", "NullBooleanField",
    "DateField", "DateTimeField",
    "ForeignKey", "OneToOneField",
})


def _is_searchable(internal_type: str) -> bool:
    """Check if a field type should be included in search_fields."""
    return internal_type in TEXT_FIELDS


def _is_filterable(field) -> bool:
    """Check if a field should be included in list_filter."""
    internal = field.get_internal_type()
    if internal in FILTER_FIELDS:
        return True
    return bool(hasattr(field, "choices") and field.choices)


def _classify_model_field(
    name: str, model: type, update_fields: list[str], pk_name: str
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Classify a single model field into admin config lists.

    Returns (list_display, search_fields, list_filter, readonly_fields) entries.
    """
    try:
        field = model._meta.get_field(name)
    except (FieldDoesNotExist, AttributeError):
        return [name], [], [], [name]

    if isinstance(field, ManyToManyField):
        return [], [], [name], []

    display = [name]
    search = [name] if _is_searchable(field.get_internal_type()) else []
    filt = [name] if _is_filterable(field) else []
    readonly = (
        [name] if name not in update_fields and name != pk_name else []
    )
    return display, search, filt, readonly


def _classify_fields(model: type) -> dict:
    """
    Derive Django Admin configuration from a ModelSerializer's field config.

    Uses ReadSerializer fields for list_display and UpdateSerializer fields
    to determine which fields are readonly.
    """
    read_fields = model.get_fields("read")
    update_fields = (
        model.get_fields("update")
        if hasattr(model, "UpdateSerializer")
        else []
    )
    pk_name = model._meta.pk.name if model._meta.pk else "id"

    list_display: list[str] = []
    search_fields: list[str] = []
    list_filter: list[str] = []
    readonly_fields: list[str] = []

    # Custom/computed fields (always readonly, always displayable)
    custom_names = {n for n, *_ in model.get_custom_fields("read")}
    custom_names |= {n for n, *_ in model.get_inline_customs("read")}
    for name in custom_names:
        list_display.append(name)
        readonly_fields.append(name)

    # Model fields
    for name in read_fields:
        display, search, filt, readonly = _classify_model_field(
            name, model, update_fields, pk_name
        )
        list_display.extend(display)
        search_fields.extend(search)
        list_filter.extend(filt)
        readonly_fields.extend(readonly)

    return {
        "list_display": tuple(list_display),
        "search_fields": tuple(search_fields),
        "list_filter": tuple(list_filter),
        "readonly_fields": tuple(readonly_fields),
    }


def model_admin_factory(model: type, **overrides) -> type[admin.ModelAdmin]:
    """
    Create a ModelAdmin class from a ModelSerializer's field config.

    Any keyword argument overrides the auto-generated value::

        AdminClass = model_admin_factory(Book, list_per_page=50)
        admin.site.register(Book, AdminClass)
    """
    config = _classify_fields(model)
    config.update(overrides)
    return type(f"{model.__name__}Admin", (admin.ModelAdmin,), config)


def register_admin(model=None, *, site=None, **overrides):
    """
    Decorator to auto-register a ModelSerializer in Django Admin.

    Can be used with or without arguments::

        @register_admin
        class Book(ModelSerializer): ...

        @register_admin(list_per_page=50)
        class Book(ModelSerializer): ...

        @register_admin(site=custom_admin_site)
        class Book(ModelSerializer): ...
    """
    target_site = site or admin.site

    def decorator(cls: type) -> type:
        admin_class = model_admin_factory(cls, **overrides)
        target_site.register(cls, admin_class)
        return cls

    # Called as @register_admin (no parentheses) — model is the class itself
    if model is not None and isinstance(model, ModelSerializerMeta):
        return decorator(model)

    # Called as @register_admin(...) with keyword args
    return decorator
