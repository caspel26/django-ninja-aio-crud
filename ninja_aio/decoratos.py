def unique_view(self: object | str, plural: bool = False):
    """
    Factory for a decorator that ensures a function name is made unique per model utility context.

    This is useful when registering multiple view functions derived from a common base
    function but requiring distinct names (e.g., for routing or introspection) tied to a model.

    Parameters
    ----------
    self : APIViewSet or str, If APIViewSet instance is provided, the model name is extracted from it.
           If a string is provided, it is used directly as the model name suffix.

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
        # Allow usage as unique_view(self_instance) or unique_view("model_name")
        if isinstance(self, str):
            suffix = self
        else:
            suffix = (
                getattr(
                    getattr(self, "model_util", None),
                    "verbose_name_view_resolver",
                    None,
                )()
                if plural
                else getattr(
                    getattr(self, "model_util", None),
                    "model_name",
                    None,
                )
            )
        if suffix:
            func.__name__ = f"{func.__name__}_{suffix}"
        return func  # Return original function (no wrapper)

    return decorator
