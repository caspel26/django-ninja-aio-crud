import asyncio
from typing import Coroutine

from django.http import HttpRequest
from ninja import Path, Query
from ninja.pagination import paginate
from ninja_aio.decorators import unique_view, decorate_view
from ninja_aio.models import ModelSerializer, ModelUtil
from ninja_aio.schemas.helpers import ObjectsQuerySchema
from ninja_aio.schemas import (
    GenericMessageSchema,
    M2MRelationSchema,
    M2MSchemaIn,
    M2MSchemaOut,
    M2MAddSchemaIn,
    M2MRemoveSchemaIn,
)
from django.db.models import QuerySet, Model


class ManyToManyAPI:
    """
    ManyToManyAPI
    -------------
    WARNING (Internal Use Only):
        This helper is currently intended solely for internal purposes. Its API,
        behaviors, and response formats may change without notice. Do not rely on
        it as a stable public interface.

    Utility class that dynamically attaches asynchronous Many-To-Many (M2M) management
    endpoints (GET / ADD / REMOVE) to a provided APIViewSet router in a Django Ninja
    async CRUD context.

    It inspects a list of M2MRelationSchema definitions and, for each relation, builds:
        - An optional paginated GET endpoint to list related objects.
        - An optional POST endpoint to add and/or remove related object primary keys.

    Core behaviors:
        - Dynamically generates per-relation filter schemas for query parameters.
        - Supports custom per-relation query filtering handlers on the parent view set
          via a `{related_name}_query_params_handler` coroutine for GET list filters.
        - Supports custom per-relation object resolution for add/remove validation via
          `{related_name}_query_handler(request, pk, instance)` used during POST to
          resolve a single related object before mutation.
        - Validates requested add/remove primary keys, producing granular success and
          error feedback.
        - Performs add/remove operations concurrently using asyncio.gather when both
          types of operations are requested in the same call.

    Attributes established at initialization:
        relations: list of M2MRelationSchema defining each relation.
        view_set: The parent APIViewSet instance from which router, pagination, model util,
                  and path schema are derived.
        router: Ninja router used to register generated endpoints.
        pagination_class: Pagination class used for GET related endpoints.
        path_schema: Pydantic schema used to validate path parameters (e.g., primary key).
        related_model_util: A ModelUtil instance cloned from the parent view set to access
                            base object retrieval helpers.
        relations_filters_schemas: Mapping of related_name -> generated Pydantic filter schema.

    Generated endpoint naming conventions:
        GET   -> get_{base_model_name}_{relation_path}
        POST  -> manage_{base_model_name}_{relation_path}

    Endpoint registration details:
        - GET: registered at `{retrieve_path}{relation_path}` with pagination; accepts Query filters.
        - POST: registered at `{retrieve_path}{relation_path}/` (trailing slash) to manage add/remove.

    All responses standardize success and error reporting for POST as:
    {
        "results": {"count": int, "details": [str, ...]},
        "errors":  {"count": int, "details": [str, ...]}
    }

    Concurrency note:
        - Add and remove operations are executed concurrently when both lists are non-empty,
          minimizing round-trip latency for bulk mutations.
        - Uses related_manager.aadd(...) and related_manager.aremove(...) inside asyncio.gather.

    Error semantics:
        - Missing related objects: reported individually.
        - Invalid operation context (e.g., removing objects not currently related or adding
          objects already related) reported per primary key.
        - Successful operations yield a corresponding success detail string per PK.

    Security / auth:
        - Each relation may optionally override auth via its schema; otherwise falls back
          to a default configured on the instance (self.default_auth).

    Pagination:
        - Applied only to GET related endpoints via @paginate(self.pagination_class).

    Extensibility:
        - Provide custom query param handling by defining an async method on the parent
          view set: `<related_name>_query_params_handler(self, queryset, filters_dict)`.
        - Provide custom per-PK resolution for POST validation by defining an async method:
          `<related_name>_query_handler(self, request, pk, instance)` returning a queryset,
          from which .afirst() is used to resolve the single target object.
        - Customize relation filtering schema via each relation's `filters` definition.

    -----------------------------------------------------------------------

    __init__(relations, view_set)
    Initialize the M2M API helper by binding core utilities from the provided view set
    and precomputing filter schemas per relation.

    Parameters:
        relations (list[M2MRelationSchema]): Definitions for each M2M relation to expose.
        view_set (APIViewSet): Parent view set containing model utilities and router.

    Side effects:
        - Captures router, pagination class, path schema from view_set.
        - Clones ModelUtil for related model operations.
        - Pre-generates filter schemas for each relation (if filters declared).

    -----------------------------------------------------------------------

    _generate_m2m_filters_schemas()
    Create a mapping of related_name -> Pydantic schema used for query filtering in
    GET related endpoints. If a relation has no filters specified, an empty schema
    (dict) is used.

    Returns:
        dict[str, BaseModel]: Generated schemas keyed by related_name.

    -----------------------------------------------------------------------

    _get_query_params_handler(related_name)
    Retrieve an optional per-relation query handler from the parent view set for GET list filters.
    Naming convention: `<related_name}_query_params_handler`.

    Parameters:
        related_name (str): The relation's attribute name on the base model.

    Returns:
        Coroutine | None: Handler to transform or filter the queryset based on query params.

    -----------------------------------------------------------------------

    _get_query_handler(related_name)
    Retrieve an optional per-relation single-object resolution handler from the parent view set
    used during POST add/remove validation. If present, it receives `(request, pk, instance)` and
    should return a queryset from which `.afirst()` will resolve the target object.

    Parameters:
        related_name (str): The relation's attribute name on the base model.

    Returns:
        Coroutine | None: Handler to resolve a single related object by pk.

    -----------------------------------------------------------------------

    _check_m2m_objs(request, objs_pks, related_model, related_manager, related_name, instance, remove=False)
    Validate requested primary keys for add/remove operations against the current
    relation state. Performs existence checks and logical consistency (e.g., prevents
    adding already-related objects or removing non-related objects). Uses `_get_query_handler`
    when available; otherwise falls back to ModelUtil(...).get_objects(...) to resolve by pk.

    Parameters:
        request (HttpRequest): Incoming request context (passed to ModelUtil for access control).
        objs_pks (list): List of primary keys to add or remove.
        related_model (ModelSerializer | Model): Model class or serializer used to resolve objects.
        related_manager (QuerySet): Related manager for the base object's M2M field.
        related_name (str): M2M field name on the base object.
        instance (ModelSerializer | Model): Base object instance (owner of the relation).
        remove (bool): If True, treat operation as removal validation.

    Returns:
        tuple[list[str], list[str], list[Model]]:
            errors      -> List of error messages per invalid PK.
            objs_detail -> List of success detail messages per valid PK.
            objs        -> List of resolved model instances to process.

    Error cases:
        - Object not found.
        - Object presence mismatch (attempting wrong operation given relation membership).

    -----------------------------------------------------------------------

    _collect_m2m(request, pks, model, related_manager, related_name, instance, remove=False)
    Wrapper around _check_m2m_objs that short-circuits on empty PK lists.

    Parameters:
        request (HttpRequest)
        pks (list): Primary keys proposed for mutation.
        model (ModelSerializer | Model)
        related_manager (QuerySet)
        related_name (str)
        instance (ModelSerializer | Model)
        remove (bool): Operation type flag.

    Returns:
        tuple[list[str], list[str], list[Model]]: See _check_m2m_objs.

    -----------------------------------------------------------------------

    _register_get_relation_view(...)
    Registers the GET endpoint for listing related objects. Applies optional
    query params handler for filtering. Uses pagination and serializes via `list_read_s`.

    -----------------------------------------------------------------------

    _register_manage_relation_view(...)
    Registers the POST endpoint for adding/removing related objects. Validates via
    `_collect_m2m` and executes mutations concurrently using `aadd`/`aremove` with
    `asyncio.gather`. Aggregates per-PK results and errors into a standardized payload.

    -----------------------------------------------------------------------

    _build_views(relation)
    Dynamically define and register the GET and/or POST endpoints for a single M2M
    relation based on the relation's schema flags (get/add/remove). Builds filter
    schemas, resolves path fragments, and binds handlers to the router with unique
    operation IDs.

    -----------------------------------------------------------------------

    _add_views()
    Iterates over all declared relations and invokes _build_views to attach endpoints.

    -----------------------------------------------------------------------

    Usage Example (conceptual):
        api = ManyToManyAPI(relations=[...], view_set=my_view_set)
        api._add_views()  # Registers all endpoints automatically during initialization flow.
    """

    def __init__(
        self,
        relations: list[M2MRelationSchema],
        view_set,
    ):
        # Import here to avoid circular imports
        from ninja_aio.views import APIViewSet

        self.relations = relations
        self.view_set: APIViewSet = view_set
        self.router = self.view_set.router
        self.pagination_class = self.view_set.pagination_class
        self.path_schema = self.view_set.path_schema
        self.default_auth = self.view_set.m2m_auth
        self.related_model_util = self.view_set.model_util
        self.relations_filters_schemas = self._generate_m2m_filters_schemas()

    @property
    def views_action_map(self):
        return {
            (True, True): ("Add or Remove", M2MSchemaIn),
            (True, False): ("Add", M2MAddSchemaIn),
            (False, True): ("Remove", M2MRemoveSchemaIn),
        }

    def _generate_m2m_filters_schemas(self):
        """
        Build per-relation filters schemas for M2M endpoints.
        """
        return {
            data.related_name: self.view_set._generate_schema(
                {} if not data.filters else data.filters,
                f"{self.related_model_util.model_name}{data.related_name.capitalize()}FiltersSchema",
            )
            for data in self.relations
        }

    def _get_query_params_handler(self, related_name: str) -> Coroutine | None:
        return getattr(self.view_set, f"{related_name}_query_params_handler", None)

    def _get_query_handler(self, related_name: str) -> Coroutine | None:
        return getattr(self.view_set, f"{related_name}_query_handler", None)

    async def _check_m2m_objs(
        self,
        request: HttpRequest,
        objs_pks: list,
        related_model: ModelSerializer | Model,
        related_manager: QuerySet,
        related_name: str,
        instance: ModelSerializer | Model,
        remove: bool = False,
    ):
        """
        Validate requested add/remove pk list for M2M operations.
        Returns (errors, details, objects_to_process).
        Uses per-PK query handler if available, else falls back to ModelUtil lookup by pk.
        """
        errors, objs_detail, objs = [], [], []
        rel_objs = [rel_obj async for rel_obj in related_manager.select_related().all()]
        rel_model_name = related_model._meta.verbose_name.capitalize()
        for obj_pk in objs_pks:
            if query_handler := self._get_query_handler(related_name):
                rel_obj = await (
                    await query_handler(
                        request,
                        obj_pk,
                        instance,
                    )
                ).afirst()
            else:
                rel_obj = await (
                    await ModelUtil(related_model).get_objects(
                        request, query_data=ObjectsQuerySchema(filters={"pk": obj_pk})
                    )
                ).afirst()
            if rel_obj is None:
                errors.append(f"{rel_model_name} with pk {obj_pk} not found.")
                continue
            if remove ^ (rel_obj in rel_objs):
                errors.append(
                    f"{rel_model_name} with pk {obj_pk} is {'not ' if remove else ''}in {self.related_model_util.model_name}"
                )
                continue
            objs.append(rel_obj)
            objs_detail.append(
                f"{rel_model_name} with pk {obj_pk} successfully {'removed' if remove else 'added'}"
            )
        return errors, objs_detail, objs

    async def _collect_m2m(
        self,
        request: HttpRequest,
        pks: list,
        reletad_model: ModelSerializer | Model,
        related_manager: QuerySet,
        related_name: str,
        instance: ModelSerializer | Model,
        remove: bool = False,
    ):
        if not pks:
            return ([], [], [])
        return await self._check_m2m_objs(
            request,
            pks,
            reletad_model,
            related_manager,
            related_name,
            instance,
            remove=remove,
        )

    def _get_api_path(self, rel_path: str, append_slash: bool = None) -> str:
        append_slash = append_slash if append_slash is not None else True
        path = (
            f"{self.view_set.path_retrieve}{rel_path}/"
            if rel_path.startswith("/")
            else f"{self.view_set.path_retrieve}/{rel_path}/"
        )
        if not append_slash:
            path = path.rstrip("/")
        return path

    def _register_get_relation_view(
        self,
        *,
        related_name: str,
        m2m_auth,
        rel_util: ModelUtil,
        rel_path: str,
        related_schema,
        filters_schema,
        append_slash: bool,
    ):
        @self.router.get(
            self._get_api_path(rel_path, append_slash=append_slash),
            response={
                200: list[related_schema],
                self.view_set.error_codes: GenericMessageSchema,
            },
            auth=m2m_auth,
            summary=f"Get {rel_util.model._meta.verbose_name_plural.capitalize()}",
            description=f"Get all related {rel_util.model._meta.verbose_name_plural.capitalize()}",
        )
        @decorate_view(
            unique_view(f"get_{self.related_model_util.model_name}_{rel_path}"),
            paginate(self.pagination_class),
        )
        async def get_related(
            request: HttpRequest,
            pk: Path[self.path_schema],  # type: ignore
            filters: Query[filters_schema] = None,  # type: ignore
        ):
            obj = await self.related_model_util.get_object(
                request, self.view_set._get_pk(pk)
            )
            related_manager = getattr(obj, related_name)
            related_qs = related_manager.all()

            query_handler = self._get_query_params_handler(related_name)
            if filters is not None and query_handler:
                if asyncio.iscoroutinefunction(query_handler):
                    related_qs = await query_handler(related_qs, filters.model_dump())
                else:
                    related_qs = query_handler(related_qs, filters.model_dump())

            return await rel_util.list_read_s(related_schema, request, related_qs)

    def _resolve_action_schema(self, add: bool, remove: bool):
        return self.views_action_map[(add, remove)]

    def _register_manage_relation_view(
        self,
        *,
        related_model: ModelSerializer | Model,
        related_name: str,
        m2m_auth,
        rel_util: ModelUtil,
        rel_path: str,
        m2m_add: bool,
        m2m_remove: bool,
    ):
        action, schema_in = self._resolve_action_schema(m2m_add, m2m_remove)
        plural = rel_util.model._meta.verbose_name_plural.capitalize()
        summary = f"{action} {plural}"

        @self.router.post(
            self._get_api_path(rel_path),
            response={
                200: M2MSchemaOut,
                self.view_set.error_codes: GenericMessageSchema,
            },
            auth=m2m_auth,
            summary=summary,
            description=summary,
        )
        @unique_view(f"manage_{self.related_model_util.model_name}_{rel_path}")
        async def manage_related(
            request: HttpRequest,
            pk: Path[self.path_schema],  # type: ignore
            data: schema_in,  # type: ignore
        ):
            obj = await self.related_model_util.get_object(
                request, self.view_set._get_pk(pk)
            )
            related_manager: QuerySet = getattr(obj, related_name)

            add_pks = getattr(data, "add", []) if m2m_add else []
            remove_pks = getattr(data, "remove", []) if m2m_remove else []

            add_errors, add_details, add_objs = await self._collect_m2m(
                request,
                add_pks,
                related_model,
                related_manager,
                related_name,
                obj,
            )
            remove_errors, remove_details, remove_objs = await self._collect_m2m(
                request,
                remove_pks,
                related_model,
                related_manager,
                related_name,
                obj,
                remove=True,
            )

            tasks = []
            if add_objs:
                tasks.append(related_manager.aadd(*add_objs))
            if remove_objs:
                tasks.append(related_manager.aremove(*remove_objs))
            if tasks:
                await asyncio.gather(*tasks)

            results = add_details + remove_details
            errors = add_errors + remove_errors
            return {
                "results": {"count": len(results), "details": results},
                "errors": {"count": len(errors), "details": errors},
            }

    def _build_views(self, relation: M2MRelationSchema):
        model = relation.model
        related_name = relation.related_name
        m2m_auth = relation.auth or self.default_auth
        rel_util = ModelUtil(model)
        rel_path = relation.path or rel_util.verbose_name_path_resolver()
        related_schema = relation.related_schema
        m2m_add, m2m_remove, m2m_get = relation.add, relation.remove, relation.get
        filters_schema = self.relations_filters_schemas.get(related_name)
        append_slash = relation.append_slash

        if m2m_get:
            self._register_get_relation_view(
                related_name=related_name,
                m2m_auth=m2m_auth,
                rel_util=rel_util,
                rel_path=rel_path,
                related_schema=related_schema,
                filters_schema=filters_schema,
                append_slash=append_slash,
            )

        if m2m_add or m2m_remove:
            self._register_manage_relation_view(
                related_model=model,
                related_name=related_name,
                m2m_auth=m2m_auth,
                rel_util=rel_util,
                rel_path=rel_path,
                m2m_add=m2m_add,
                m2m_remove=m2m_remove,
            )

    def _add_views(self):
        for relation in self.relations:
            self._build_views(relation)
