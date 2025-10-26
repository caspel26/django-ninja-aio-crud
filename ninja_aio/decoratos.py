def unique_view(self: object | str, plural: bool = False):
    """
    Return a decorator that appends a model-specific suffix to a function's __name__ for uniqueness.

    This is helpful when multiple view functions share a common base name but must be
    distinct (e.g., for route registration, debugging, or introspection) per model context.

    self : object | str
        - If a string, it is used directly as the suffix.
        - If an object, its `model_util` attribute is inspected for:
            * model_util.model_name (when plural is False)
            * model_util.verbose_name_view_resolver() (when plural is True)
          Missing attributes or call failures result in no suffix being applied.
    plural : bool, default False
        If True and `self` is an object with `model_util.verbose_name_view_resolver`,
        the resolved pluralized verbose name is used; otherwise the singular model name
        (model_util.model_name) is used.

    Callable[[Callable], Callable]
        A decorator. When applied, it mutates the target function's __name__ in place to:
        "<original_name>_<suffix>" if a suffix is resolved. If no suffix is found, the
        function is returned unchanged.

    - Does NOT wrap or alter the call signature or async/sync nature of the function.
    - Performs a simple in-place mutation of func.__name__ before returning the original function.
    - No metadata (e.g., __doc__, __qualname__) is altered besides __name__.

    Suffix Resolution Logic
    -----------------------
    1. If `self` is a str: suffix = self
    2. Else if `self` has `model_util`:
       - plural == True: suffix = model_util.verbose_name_view_resolver()
       - plural == False: suffix = model_util.model_name
    3. If resolution fails or yields a falsy value, no mutation occurs.

    Side Effects
    ------------
    - Modifies function.__name__, which can affect:
      - Debugging output
      - Route registration relying on function names
      - Tools expecting the original name
    - Because mutation is in place, reusing the original function object elsewhere
      may produce unexpected naming.

    Examples
    # Using a string suffix directly
    @unique_view("book")
    def list_items():

    # Using an object with model_util.model_name
    @unique_view(viewset_instance)  # where viewset_instance.model_util.model_name == "author"
    def retrieve():
    # Resulting function name: "retrieve_author"

    # Using plural form via verbose_name_view_resolver()
    @unique_view(viewset_instance, plural=True)  # e.g., returns "authors"
    def list():
    # Resulting function name: "list_authors"

    Caveats
    - If the underlying attributes or resolver callable raise exceptions, they are not caught.
    - Ensure that the modified name does not conflict with other functions after decoration.
    - Use cautiously when decorators relying on original __name__ appear earlier in the chain.
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
