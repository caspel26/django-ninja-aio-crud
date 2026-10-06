import asyncio
import logging
from functools import partial, wraps

from django.db import transaction
from asgiref.sync import async_to_sync, sync_to_async

logger = logging.getLogger("ninja_aio.decorators")
_CANCELLED = object()


async def _await_call(func, args, kwargs):
    return await func(*args, **kwargs)


def _run_atomic(func, args, kwargs, using):
    try:
        with transaction.atomic(using=using):
            return async_to_sync(_await_call)(func, args, kwargs)
    except asyncio.CancelledError:
        # Complete rollback before propagating cancellation on the event loop.
        # A CancelledError on the executor's Future can otherwise be left
        # unconsumed when sync_to_async cancels its shielded await.
        return _CANCELLED


async def arun_atomic(func, *args, using=None, **kwargs):
    """Run a coroutine with transaction ownership held by its database worker.

    Bridging only Atomic.__enter__/__exit__ lets unrelated tasks interleave
    writes on the same connection. Hold the worker for the entire operation;
    async_to_sync routes this coroutine's ORM calls back to that worker while
    sibling operations wait on its original executor. Nested calls retain
    Django's savepoint semantics and hooks still run on the caller's event loop.
    """
    result = await sync_to_async(_run_atomic)(func, args, kwargs, using)
    if result is _CANCELLED:
        raise asyncio.CancelledError
    return result


def aatomic(func):
    """
    Decorator that executes the wrapped async function inside an asynchronous atomic
    database transaction context.

    This is useful when you want all ORM write operations performed by the coroutine
    to either fully succeed or fully roll back on error, preserving data integrity.

    Parameters:
        func (Callable): The asynchronous function to wrap.

    Returns:
        Callable: A new async function that, when awaited, runs inside a
        database transaction owned by a synchronous worker.

    Behavior:
        - Opens an async atomic transaction before invoking the wrapped coroutine.
        - Commits if the coroutine completes successfully.
        - Rolls back if an exception is raised and propagates the original exception.

    Example:
        @aatomic
        async def create_order(user_id: int, items: list[Item]):
            # Perform multiple related DB writes atomically
            ...

    Operations sharing a database worker run sequentially. Hooks must not wait
    for an independent database operation queued on that same worker.
    Only use on async functions.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger.debug(f"Entering atomic transaction for {func.__qualname__}")
        return await arun_atomic(partial(func, *args, **kwargs))

    return wrapper


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


def decorate_view(*decorators):
    """
    Compose and apply multiple decorators to a view (sync or async) without adding an extra wrapper.

    This utility was introduced to support class-based patterns where Django Ninja’s
    built-in `decorate_view` does not fit well. For APIs implemented with vanilla
    Django Ninja (function-based style), you should continue using Django Ninja’s
    native `decorate_view`.

    Behavior:
    - Applies decorators in the same order as Python’s stacking syntax:
        @d1
        @d2
      is equivalent to: view = d1(d2(view))
    - Supports both synchronous and asynchronous views.
    - Ignores None values, enabling conditional decoration.
    - Does not introduce an additional wrapper; composition depends on each
      decorator for signature/metadata preservation (e.g., using functools.wraps).

        *decorators: Decorator callables to apply to the target view. Any None values
            are skipped.

        Callable: A decorator that applies the provided decorators in Python stacking order.

        Method usage in class-based patterns:

    Args:
        *decorators: Decorator callables to apply to the target view. Any None
            values are skipped.

    Returns:
        A decorator that applies the provided decorators in Python stacking order.

    Examples:
        Basic usage:
            class MyAPIViewSet(APIViewSet):
                api = api
                model = MyModel

                def views(self):
                    @self.router.get('some-endpoint/')
                    @decorate_view(authenticate, log_request)
                    async def some_view(request):
                        ...

        Conditional decoration (skips None):
            class MyAPIViewSet(APIViewSet):
                api = api
                model = MyModel
                cache_dec = cache_page(60) if settings.ENABLE_CACHE else None
                def views(self):
                    @self.router.get('data/')
                    @decorate_view(self.cache_dec, authenticate)
                    async def data_view(request):
                        ...

    Notes:
        - Each decorator is applied in the order provided, with the first decorator
          wrapping the result of the second, and so on.
        - Ensure that each decorator is compatible with the view’s sync/async nature.
    """

    def _decorator(view):
        wrapped = view
        for dec in reversed(decorators):
            if dec is None:
                continue
            wrapped = dec(wrapped)
        return wrapped

    return _decorator
