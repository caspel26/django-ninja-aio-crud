"""
Reactive Model Hooks
====================

Decorators for declaring lifecycle hooks directly on ModelSerializer
and Serializer classes. Hooks fire automatically during CRUD operations.

Usage on ModelSerializer::

    class Article(ModelSerializer):
        @on_create
        async def notify_author(self):
            await send_email(self.author.email, "Article created")

        @on_update("status")
        async def handle_publish(self):
            if self.status == "published":
                await invalidate_cache(f"article:{self.pk}")

        @on_delete
        async def cleanup(self):
            await delete_s3_images(self.pk)

Usage on Serializer (receives instance as parameter)::

    class ArticleSerializer(Serializer):
        @on_create
        async def notify_author(self, instance):
            await send_email(instance.author.email, "Article created")

        @on_update("status")
        async def handle_publish(self, instance):
            if instance.status == "published":
                await invalidate_cache(f"article:{instance.pk}")
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar

from asgiref.sync import sync_to_async, async_to_sync
from django.db.models.signals import post_save, post_delete

logger = logging.getLogger("ninja_aio.models")

_HOOK_ATTR = "_reactive_hook_meta"


class _HookMeta:
    """Metadata attached to a decorated hook method."""

    __slots__ = ("event", "fields")

    def __init__(self, event: str, fields: tuple[str, ...] | None = None):
        self.event = event
        self.fields = fields


def on_create(func):
    """Mark a method to fire after instance creation."""
    setattr(func, _HOOK_ATTR, _HookMeta("create"))
    return func


def on_delete(func):
    """Mark a method to fire after instance deletion."""
    setattr(func, _HOOK_ATTR, _HookMeta("delete"))
    return func


def on_update(_func_or_field=None, *extra_fields):
    """Mark a method to fire after instance update.

    Usage::

        @on_update                       # fires on ANY update
        @on_update("status")             # fires only when status changes
        @on_update("status", "priority") # fires when either changes
    """
    if callable(_func_or_field):
        setattr(_func_or_field, _HOOK_ATTR, _HookMeta("update"))
        return _func_or_field

    fields = (
        (_func_or_field,) + extra_fields if _func_or_field else extra_fields
    )

    def decorator(func):
        setattr(func, _HOOK_ATTR, _HookMeta("update", fields))
        return func

    return decorator


def collect_reactive_hooks(cls) -> dict:
    """Scan a class for reactive hook decorators.

    Returns a dict::

        {
            "create": ["method_name", ...],
            "update_any": ["method_name", ...],
            "update_field": {"status": ["method_name", ...], ...},
            "delete": ["method_name", ...],
        }

    Methods are collected in definition order using ``vars(cls)`` for the
    class's own methods, then parent classes in MRO order.
    """
    hooks = {"create": [], "update_any": [], "update_field": {}, "delete": []}
    seen = set()

    for klass in reversed(cls.__mro__):
        for name, method in vars(klass).items():
            if name in seen:
                continue
            meta = getattr(method, _HOOK_ATTR, None)
            if meta is None:
                continue
            seen.add(name)

            if meta.event == "create":
                hooks["create"].append(name)
            elif meta.event == "delete":
                hooks["delete"].append(name)
            elif meta.event == "update":
                if meta.fields:
                    for field in meta.fields:
                        hooks["update_field"].setdefault(field, []).append(name)
                else:
                    hooks["update_any"].append(name)

    return hooks


async def execute_reactive_hooks(
    target, hook_names: list[str], instance=None
) -> None:
    """Execute a list of hook methods sequentially on *target*.

    Parameters
    ----------
    target
        The object whose methods will be called (ModelSerializer instance
        or Serializer instance).
    hook_names : list[str]
        Method names to call, in order.
    instance : Model, optional
        For Serializer hooks, the model instance passed as first argument.
    """
    for name in hook_names:
        method = getattr(target, name)
        if asyncio.iscoroutinefunction(method):
            if instance is not None:
                await method(instance)
            else:
                await method()
        else:
            if instance is not None:
                await sync_to_async(method)(instance)
            else:
                await sync_to_async(method)()


def detect_changed_fields(
    obj, payload: dict, watched_fields: dict[str, list[str]]
) -> set[str]:
    """Compare old attribute values on *obj* with new values in *payload*.

    Returns the set of field names that actually changed. This avoids
    DB queries by using the already-loaded object attributes.
    """
    changed = set()
    for field in watched_fields:
        if field in payload:
            old_val = getattr(obj, field, None)
            new_val = payload[field]
            if old_val != new_val:
                changed.add(field)
    return changed


async def fire_update_hooks(target, changed_fields: set, hooks: dict, instance=None):
    """Fire field-specific and generic update hooks.

    Parameters
    ----------
    target
        ModelSerializer instance or Serializer instance.
    changed_fields : set
        Fields that actually changed.
    hooks : dict
        The ``_reactive_hooks`` dict from the class.
    instance
        For Serializer, the model instance.
    """
    for field in changed_fields:
        field_hooks = hooks["update_field"].get(field, [])
        if field_hooks:
            logger.debug(f"Firing @on_update('{field}') hooks on {type(target).__name__}")
            await execute_reactive_hooks(target, field_hooks, instance)

    if hooks["update_any"]:
        logger.debug(f"Firing @on_update hooks on {type(target).__name__}")
        await execute_reactive_hooks(target, hooks["update_any"], instance)


def _run_hook_sync(method, instance=None):
    """Run a single hook method, handling both sync and async."""
    if asyncio.iscoroutinefunction(method):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in an async context (API path) — skip,
            # the async path in utils.py already fired this hook.
            return
        # No event loop (shell, management command) — run synchronously
        if instance is not None:
            async_to_sync(method)(instance)
        else:
            async_to_sync(method)()
    else:
        if instance is not None:
            method(instance)
        else:
            method()


def _execute_hooks_sync(target, hook_names: list[str], instance=None):
    """Execute hook methods synchronously (for signal handlers)."""
    for name in hook_names:
        method = getattr(target, name)
        _run_hook_sync(method, instance)


# When True, signal handlers skip execution (API path fires hooks directly)
_api_hooks_active: ContextVar[bool] = ContextVar("_api_hooks_active", default=False)


@asynccontextmanager
async def suppress_signals():
    """Suppress reactive hook signals during API operations.

    Prevents double-firing: the async API path fires hooks directly
    with full context (field-change detection), so Django signals
    should be skipped.
    """
    token = _api_hooks_active.set(True)
    try:
        yield
    finally:
        _api_hooks_active.reset(token)


def get_hooks(model_or_serializer) -> dict | None:
    """Get reactive hooks dict from a model or serializer class, or None."""
    hooks = getattr(model_or_serializer, "_reactive_hooks", None)
    if not hooks:
        return None
    if hooks["create"] or hooks["update_any"] or hooks["update_field"] or hooks["delete"]:
        return hooks
    return None


def _on_post_save(sender, instance, created, **kwargs):
    """Django post_save signal handler — fires @on_create or @on_update hooks.

    Skipped when ``_api_hooks_active`` is True (the async API path in
    utils.py fires hooks directly with full field-change detection).
    """
    if _api_hooks_active.get(False):
        return

    hooks = getattr(sender, "_reactive_hooks", None)
    if not hooks:
        return

    if created:
        if hooks["create"]:
            logger.debug(f"Signal post_save (create) firing hooks on {sender.__name__}")
            _execute_hooks_sync(instance, hooks["create"])
    else:
        if hooks["update_any"]:
            logger.debug(f"Signal post_save (update) firing hooks on {sender.__name__}")
            _execute_hooks_sync(instance, hooks["update_any"])


def _on_post_delete(sender, instance, **kwargs):
    """Django post_delete signal handler — fires @on_delete hooks.

    Skipped when ``_api_hooks_active`` is True.
    """
    if _api_hooks_active.get(False):
        return

    hooks = getattr(sender, "_reactive_hooks", None)
    if not hooks:
        return

    if hooks["delete"]:
        logger.debug(f"Signal post_delete firing hooks on {sender.__name__}")
        _execute_hooks_sync(instance, hooks["delete"])


def register_signals(model_class):
    """Connect post_save and post_delete signals for a ModelSerializer class.

    Called from ModelSerializer.__init_subclass__ after hook collection.
    Only connects signals if the class has at least one reactive hook.
    """
    hooks = getattr(model_class, "_reactive_hooks", None)
    if not hooks:
        return

    has_hooks = (
        hooks["create"]
        or hooks["update_any"]
        or hooks["update_field"]
        or hooks["delete"]
    )
    if not has_hooks:
        return

    post_save.connect(_on_post_save, sender=model_class, weak=False)
    post_delete.connect(_on_post_delete, sender=model_class, weak=False)
