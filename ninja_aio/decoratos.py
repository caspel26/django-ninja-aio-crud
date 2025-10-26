import asyncio
import functools


def unique_view(self):
    """
    Factory for a decorator that ensures a function name is made unique per model utility context.

    This is useful when registering multiple view functions derived from a common base
    function but requiring distinct names (e.g., for routing or introspection) tied to a model.

    Parameters
    ----------
    self : APIViewSet

    Returns
    -------
    Callable
        A decorator. When applied to a function (sync or async), it returns a wrapped version
        of that function preserving its original behavior while modifying `__name__` to:
        "<original_name>_<model_name>".

    Behavior
    --------
    - Detects whether the decorated function is asynchronous and wraps accordingly.
    - Applies functools.wraps to preserve metadata (e.g., __module__, __qualname__, __doc__).
    - Updates the resulting wrapper's __name__ to include the associated model name, aiding
      in disambiguation during registration or debugging.

    Example
    -------
    @unique_view(self_instance)
    def list_items(...):
        ...

    Resulting function name (if model_name == "book"):
        list_items_book
    """
    def decorator(func):
        # optional wrapper if you want to preserve original function object
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
        wrapper.__name__ = f"{func.__name__}_{self.model_util.model_name}"
        return wrapper
    return decorator