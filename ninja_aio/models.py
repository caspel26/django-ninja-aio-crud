import asyncio
import base64
from typing import Any

from ninja import Schema
from ninja.orm import create_schema

from django.db import models
from django.http import HttpRequest
from django.core.exceptions import ObjectDoesNotExist
from asgiref.sync import sync_to_async
from django.db.models.fields.related_descriptors import (
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    ManyToManyDescriptor,
    ForwardManyToOneDescriptor,
    ForwardOneToOneDescriptor,
)

from .exceptions import SerializeError, NotFoundError
from .types import S_TYPES, F_TYPES, SCHEMA_TYPES, ModelSerializerMeta


async def agetattr(obj, name: str, default=None):
    return await sync_to_async(getattr)(obj, name, default)


class ModelUtil:
    """
    ModelUtil
    =========
    Async utility bound to a Django model class (or a ModelSerializer subclass)
    providing high‑level CRUD helpers plus (de)serialization glue for Django Ninja.

    Overview
    --------
    Central responsibilities:
    - Introspect model metadata (field list, pk name, verbose names).
    - Normalize inbound payloads (custom / optional fields, FK resolution, base64 decoding).
    - Normalize outbound payloads (resolve nested relation dicts into model instances).
    - Prefetch reverse relations to mitigate N+1 issues.
    - Invoke optional serializer hooks: custom_actions(), post_create(), queryset_request().

    Compatible With
    ---------------
    - Plain Django models.
    - Models using ModelSerializerMeta exposing:
        get_fields(mode), is_custom(name), is_optional(name),
        queryset_request(request), custom_actions(payload), post_create().

    Key Methods
    -----------
    - get_object(request, pk=None, filters=None, getters=None, with_qs_request=True)
        Returns a single object (when pk/getters) or a queryset (otherwise), with
        select_related + prefetch_related applied.
    - get_reverse_relations()
        Discovers reverse relation names for safe prefetch_related usage.
    - parse_input_data(request, data)
        Converts a Schema into a model-ready dict:
          * Strips custom + ignored optionals.
          * Decodes BinaryField (base64 -> bytes).
          * Replaces FK ids with related instances.
        Returns (payload, customs_dict).
    - parse_output_data(request, data)
        Post-processes serialized output; replaces nested FK/OneToOne dicts
        with authoritative related instances and rewrites nested FK keys to <name>_id.
    - create_s / read_s / update_s / delete_s
        High-level async CRUD operations wrapping the above transformations and hooks.

    Error Handling
    --------------
    - Missing objects -> SerializeError({...}, 404).
    - Bad base64 -> SerializeError({...}, 400).

    Performance Notes
    -----------------
    - Each FK in parse_input_data triggers its own async fetch.
    - Reverse relation prefetching is opportunistic; trim serializable fields
      if over-fetching becomes an issue.

    Return Shapes
    -------------
    - create_s / read_s / update_s -> dict (post-processed schema dump).
    - delete_s -> None.
    - get_object -> model instance or queryset.

    Design Choices
    --------------
    - Stateless aside from holding the target model (safe to instantiate per request).
    - Avoids caching; callers may add caching where profiling justifies it.
    - Treats absent optional fields as "leave unchanged" (update) or "omit" (create).

    Assumptions
    -----------
    - Schema provides model_dump(mode="json").
    - Django async ORM (Django 4.1+).
    - BinaryField inputs are base64 strings.
    - Related primary keys are simple scalars on input.

    """

    def __init__(self, model: type["ModelSerializer"] | models.Model):
        self.model = model

    @property
    def serializable_fields(self):
        if isinstance(self.model, ModelSerializerMeta):
            return self.model.get_fields("read")
        return self.model_fields

    @property
    def model_fields(self):
        return [field.name for field in self.model._meta.get_fields()]

    @property
    def model_name(self) -> str:
        return self.model._meta.model_name

    @property
    def model_pk_name(self) -> str:
        return self.model._meta.pk.attname

    @property
    def model_verbose_name_plural(self) -> str:
        return self.model._meta.verbose_name_plural

    def verbose_name_path_resolver(self) -> str:
        return "-".join(self.model_verbose_name_plural.split(" "))

    def verbose_name_view_resolver(self) -> str:
        return self.model_verbose_name_plural.replace(" ", "")

    async def get_object(
        self,
        request: HttpRequest,
        pk: int | str = None,
        filters: dict = None,
        getters: dict = None,
        with_qs_request=True,
    ) -> (
        type["ModelSerializer"]
        | models.Model
        | models.QuerySet[type["ModelSerializer"] | models.Model]
    ):
        get_q = {self.model_pk_name: pk} if pk is not None else {}
        if getters:
            get_q |= getters

        obj_qs = self.model.objects.select_related()
        if isinstance(self.model, ModelSerializerMeta) and with_qs_request:
            obj_qs = await self.model.queryset_request(request)

        obj_qs = obj_qs.prefetch_related(*self.get_reverse_relations())
        if filters:
            obj_qs = obj_qs.filter(**filters)

        if not get_q:
            return obj_qs

        try:
            obj = await obj_qs.aget(**get_q)
        except ObjectDoesNotExist:
            raise NotFoundError(self.model)

        return obj

    def get_reverse_relations(self) -> list[str]:
        reverse_rels = []
        for f in self.serializable_fields:
            field_obj = getattr(self.model, f)
            if isinstance(field_obj, ManyToManyDescriptor):
                reverse_rels.append(f)
                continue
            if isinstance(field_obj, ReverseManyToOneDescriptor):
                reverse_rels.append(field_obj.field._related_name)
                continue
            if isinstance(field_obj, ReverseOneToOneDescriptor):
                reverse_rels.append(field_obj.related.name)
        return reverse_rels

    async def parse_input_data(self, request: HttpRequest, data: Schema):
        payload = data.model_dump(mode="json")
        customs = {}
        optionals = []
        if isinstance(self.model, ModelSerializerMeta):
            customs = {
                k: v
                for k, v in payload.items()
                if self.model.is_custom(k) and k not in self.model_fields
            }
            optionals = [
                k for k, v in payload.items() if self.model.is_optional(k) and v is None
            ]
        for k, v in payload.items():
            if isinstance(self.model, ModelSerializerMeta):
                if self.model.is_custom(k) and k not in self.model_fields:
                    continue
                if self.model.is_optional(k) and v is None:
                    continue
            field_obj = (await agetattr(self.model, k)).field
            if isinstance(field_obj, models.BinaryField):
                try:
                    payload |= {k: base64.b64decode(v)}
                except Exception as exc:
                    raise SerializeError({k: ". ".join(exc.args)}, 400)
            if isinstance(field_obj, models.ForeignKey):
                rel_util = ModelUtil(field_obj.related_model)
                rel: ModelSerializer = await rel_util.get_object(
                    request, v, with_qs_request=False
                )
                payload |= {k: rel}
        new_payload = {
            k: v for k, v in payload.items() if k not in (customs.keys() or optionals)
        }
        return new_payload, customs

    async def parse_output_data(self, request: HttpRequest, data: Schema):
        olds_k: list[dict] = []
        payload = data.model_dump(mode="json")
        for k, v in payload.items():
            try:
                field_obj = (await agetattr(self.model, k)).field
            except AttributeError:
                try:
                    field_obj = (await agetattr(self.model, k)).related
                except AttributeError:
                    pass
            if isinstance(v, dict) and (
                isinstance(field_obj, models.ForeignKey)
                or isinstance(field_obj, models.OneToOneField)
            ):
                rel_util = ModelUtil(field_obj.related_model)
                rel: ModelSerializer = await rel_util.get_object(
                    request, v.get(rel_util.model_pk_name)
                )
                if isinstance(field_obj, models.ForeignKey):
                    for rel_k, rel_v in v.items():
                        field_rel_obj = await agetattr(rel, rel_k)
                        if isinstance(field_rel_obj, models.ForeignKey):
                            olds_k.append({rel_k: rel_v})
                    for obj in olds_k:
                        for old_k, old_v in obj.items():
                            v.pop(old_k)
                            v |= {f"{old_k}_id": old_v}
                    olds_k = []
                payload |= {k: rel}
        return payload

    async def create_s(self, request: HttpRequest, data: Schema, obj_schema: Schema):
        payload, customs = await self.parse_input_data(request, data)
        pk = (await self.model.objects.acreate(**payload)).pk
        obj = await self.get_object(request, pk)
        if isinstance(self.model, ModelSerializerMeta):
            await asyncio.gather(obj.custom_actions(customs), obj.post_create())
        return await self.read_s(request, obj, obj_schema)

    async def read_s(
        self,
        request: HttpRequest,
        obj: type["ModelSerializer"],
        obj_schema: Schema,
    ):
        if obj_schema is None:
            raise SerializeError({"obj_schema": "must be provided"}, 400)
        return await self.parse_output_data(
            request, await sync_to_async(obj_schema.from_orm)(obj)
        )

    async def update_s(
        self, request: HttpRequest, data: Schema, pk: int | str, obj_schema: Schema
    ):
        obj = await self.get_object(request, pk)
        payload, customs = await self.parse_input_data(request, data)
        for k, v in payload.items():
            if v is not None:
                setattr(obj, k, v)
        if isinstance(self.model, ModelSerializerMeta):
            await obj.custom_actions(customs)
        await obj.asave()
        updated_object = await self.get_object(request, pk)
        return await self.read_s(request, updated_object, obj_schema)

    async def delete_s(self, request: HttpRequest, pk: int | str):
        obj = await self.get_object(request, pk)
        await obj.adelete()
        return None


class ModelSerializer(models.Model, metaclass=ModelSerializerMeta):
    """
    ModelSerializer
    =================
    Abstract mixin for Django models centralizing (on the model class itself) the
    declarative configuration required to auto-generate create / update / read /
    related schemas.

    Goals
    - Remove duplication between Model and separate serializer classes.
    - Provide clear extension points (sync + async hooks, custom synthetic fields).

    Inner configuration classes
    - CreateSerializer
        fields    : required model fields on create
        optionals : optional model fields (accepted if present; ignored if None)
        customs   : [(name, type, default)] synthetic (non‑model) inputs
        excludes  : model fields disallowed on create
    - UpdateSerializer (same structure; usually use optionals for PATCH-like behavior)
    - ReadSerializer
        fields    : model fields to expose
        excludes  : fields always excluded (e.g. password)
        customs   : [(name, type, default)] computed outputs (property > callable > default)

    Generated schema helpers
    - generate_create_s()   -> input schema ("In")
    - generate_update_s()   -> input schema for partial/full update ("Patch")
    - generate_read_s()     -> detailed output schema ("Out")
    - generate_related_s()  -> compact nested schema ("Related")

    Relation handling (only if related model is also a ModelSerializer)
    - Forward FK / OneToOne serialized as single nested objects
    - Reverse OneToOne / Reverse FK / M2M serialized as single or list
    - Relations skipped if related model exposes no read/custom fields

    Classification helpers
    - is_custom(field)   -> True if declared in create/update customs
    - is_optional(field) -> True if declared in create/update optionals

    Sync lifecycle hooks (override as needed)
      save():
        on_create_before_save()  (only first insert)
        before_save()
        super().save()
        on_create_after_save()   (only first insert)
        after_save()
      delete():
        super().delete()
        on_delete()

    Async extension points
    - queryset_request(request): request-scoped queryset filtering
    - post_create(): async logic after creation
    - custom_actions(payload_customs): react to synthetic fields

    Utilities
    - has_changed(field): compares in-memory value vs DB persisted value
    - verbose_name_path_resolver(): slugified plural verbose name

    Implementation notes
    - If both fields and excludes are empty (create/update), optionals are used as the base.
    - customs + optionals are passed as custom_fields to the schema factory.
    - Nested relation schemas generated only if the related model explicitly declares
      readable or custom fields.

    Minimal example
    ```python
    from django.db import models
    from ninja_aio.models import ModelSerializer


    class User(ModelSerializer):
        username = models.CharField(max_length=150, unique=True)
        email = models.EmailField(unique=True)

        class CreateSerializer:
            fields = ["username", "email"]

        class ReadSerializer:
            fields = ["id", "username", "email"]

        def __str__(self):
            return self.username
    ```
    -------------------------------------
    Conceptual Equivalent (Ninja example)
    Using django-ninja you might otherwise write:
    ```python
    from ninja import ModelSchema
    from api.models import User


    class UserIn(ModelSchema):
        class Meta:
            model = User
            fields = ["username", "email"]


    class UserOut(ModelSchema):
        class Meta:
            model = User
            model_fields = ["id", "username", "email"]
    ```

    Summary
    Centralizes serialization intent on the model, reducing boilerplate and keeping
    API and model definitions consistent.
    """

    class Meta:
        abstract = True

    class CreateSerializer:
        """Configuration container describing how to build a create (input) schema for a model.

        Purpose
        -------
        Describes which fields are accepted (and in what form) when creating a new
        instance. A factory/metaclass can read this configuration to generate a
        Pydantic / Ninja input schema.

        Attributes
        ----------
        fields : list[str]
            Explicit REQUIRED model field names for creation. If empty, the
            implementation may infer required fields from the model (excluding
            auto / read-only fields). Prefer being explicit.
        optionals : list[tuple[str, type]]
            Model fields allowed on create but not required. Each tuple:
                (field_name, python_type)
            If omitted in the payload they are ignored; if present with null/None
            the caller signals an intentional null (subject to model constraints).
        customs : list[tuple[str, type, Any]]
            Non-model / synthetic input fields driving creation logic (e.g.,
            password confirmation, initial related IDs, flags). Each tuple:
                (name, python_type, default_value)
            Resolution order (implementation-dependent):
                1. Value provided by the incoming payload.
                2. If default_value is callable -> invoked (passing model class or
                   context if supported).
                3. Literal default_value.
            These values are typically consumed inside custom_actions or post_create
            hooks and are NOT persisted directly unless you do so manually.
        excludes : list[str]
            Model field names that must be rejected on create (e.g., "id",
            audit fields, computed columns).

        Recommended Conventions
        -----------------------
        - Always exclude primary keys and auto-managed timestamps.
        - Keep customs minimal and clearly documented.
        - Use optionals instead of putting nullable fields in fields if they are
          not logically required for initial creation.

        Extensibility
        -------------
        A higher-level builder can:
            1. Collect fields + optionals + customs.
            2. Build a schema where fields are required, optionals are Optional[…],
               and customs become additional inputs not mapped directly to the model.
        """

        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []
        optionals: list[tuple[str, type]] = []
        excludes: list[str] = []

    class ReadSerializer:
        """Configuration container describing how to build a read (output) schema for a model.

        Attributes
        ---------
        fields : list[str]
            Explicit model field names to include in the read schema. If empty, an
            implementation may choose to include all model fields (or none, depending
            on the consuming logic).
        excludes : list[str]
            Model field names to force-exclude even if they would otherwise be included
            (e.g., sensitive columns like password, secrets, internal flags).
        customs : list[tuple[str, type, Any]]
            Additional computed / synthetic attributes to append to the serialized
            output. Each tuple is:
                (attribute_name, python_type, default_value)
            The attribute is resolved in the following preferred order (implementation
            dependent):
                1. Attribute / property on the model instance with that name.
                2. Callable (if the default_value is a callable) invoked to produce a value.
                3. Fallback to the literal default_value.
            Example:
                customs = [
                    ("full_name", str, lambda obj: f"{obj.first_name} {obj.last_name}".strip())
                ]

        Conceptual Equivalent (Ninja example)
        -------------------------------------
        Using django-ninja you might otherwise write:

        ```python
        from ninja import ModelSchema
        from api.models import User


        class UserOut(ModelSchema):
            class Meta:
                model = User
                model_fields = ["id", "username", "email"]
        ```

        This ReadSerializer object centralizes the same intent in a lightweight,
        framework-agnostic configuration primitive that can be inspected to build
        schemas dynamically.

        Recommended Conventions
        -----------------------
        - Keep fields minimal; prefer explicit inclusion over implicit broad exposure.
        - Use excludes as a safety net (e.g., always exclude "password").
        - For customs, always specify a concrete python_type for better downstream
          validation / OpenAPI generation.
        - Prefer callables as default_value when computing derived data; use simple
          literals only for static fallbacks.

        Extensibility Notes
        -------------------
        A higher-level factory or metaclass can:
            1. Read these lists.
            2. Reflect on the model.
            3. Generate a Pydantic / Ninja schema class at runtime.
        This separation enables cleaner unit testing (the config is pure data) and
        reduces coupling to a specific serialization framework."""

        fields: list[str] = []
        excludes: list[str] = []
        customs: list[tuple[str, type, Any]] = []

    class UpdateSerializer:
        """Configuration container describing how to build an update (partial/full) input schema.

        Purpose
        -------
        Defines which fields can be changed and how they are treated when updating
        an existing instance (PATCH / PUT–style operations).

        Attributes
        ----------
        fields : list[str]
            Explicit REQUIRED fields for an update operation (rare; most updates are
            partial so this is often left empty). If non-empty, these must be present
            in the payload.
        optionals : list[tuple[str, type]]
            Updatable fields that are optional (most typical case). Omitted fields
            are left untouched. Provided null/None values indicate an explicit attempt
            to nullify (subject to model constraints).
        customs : list[tuple[str, type, Any]]
            Non-model / instruction fields guiding update behavior (e.g., "rotate_key",
            "regenerate_token"). Each tuple:
                (name, python_type, default_value)
            Resolution order mirrors CreateSerializer (payload > callable > literal).
            Typically consumed in custom_actions before or after saving.
        excludes : list[str]
            Fields that must never be updated (immutable or managed fields).

        Recommended Conventions
        -----------------------
        - Prefer listing editable columns in optionals rather than fields to facilitate
          partial updates.
        - Use customs for operational flags (e.g., "reset_password": bool).
        - Keep excludes synchronized with CreateSerializer excludes where appropriate.

        Extensibility
        -------------
        A schema builder can:
            1. Treat fields as required.
            2. Treat optionals as Optional[…].
            3. Inject customs as additional validated inputs.
            4. Enforce excludes by rejecting them if present in incoming data.
        """

        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []
        optionals: list[tuple[str, type]] = []
        excludes: list[str] = []

    @property
    def has_custom_fields_create(self):
        return hasattr(self.CreateSerializer, "customs")

    @property
    def has_custom_fields_update(self):
        return hasattr(self.UpdateSerializer, "customs")

    @property
    def has_custom_fields(self):
        return self.has_custom_fields_create or self.has_custom_fields_update

    @property
    def has_optional_fields_create(self):
        return hasattr(self.CreateSerializer, "optionals")

    @property
    def has_optional_fields_update(self):
        return hasattr(self.UpdateSerializer, "optionals")

    @property
    def has_optional_fields(self):
        return self.has_optional_fields_create or self.has_optional_fields_update

    @classmethod
    def _get_fields(cls, s_type: type[S_TYPES], f_type: type[F_TYPES]):
        match s_type:
            case "create":
                fields = getattr(cls.CreateSerializer, f_type, [])
            case "update":
                fields = getattr(cls.UpdateSerializer, f_type, [])
            case "read":
                fields = getattr(cls.ReadSerializer, f_type, [])
        return fields

    @classmethod
    def _is_special_field(
        cls, s_type: type[S_TYPES], field: str, f_type: type[F_TYPES]
    ):
        special_fields = cls._get_fields(s_type, f_type)
        return any(field in special_f for special_f in special_fields)

    @classmethod
    def _generate_model_schema(
        cls,
        schema_type: type[SCHEMA_TYPES],
        depth: int = None,
    ) -> Schema:
        match schema_type:
            case "In":
                s_type = "create"
            case "Patch":
                s_type = "update"
            case "Out":
                fields, reverse_rels, excludes, customs = cls.get_schema_out_data()
                if not fields and not reverse_rels and not excludes and not customs:
                    return None
                return create_schema(
                    model=cls,
                    name=f"{cls._meta.model_name}SchemaOut",
                    depth=depth,
                    fields=fields,
                    custom_fields=reverse_rels + customs,
                    exclude=excludes,
                )
            case "Related":
                fields, customs = cls.get_related_schema_data()
                if not fields and not customs:
                    return None
                return create_schema(
                    model=cls,
                    name=f"{cls._meta.model_name}SchemaRelated",
                    fields=fields,
                    custom_fields=customs,
                )

        fields = cls.get_fields(s_type)
        optionals = cls.get_optional_fields(s_type)
        customs = cls.get_custom_fields(s_type) + optionals
        excludes = cls.get_excluded_fields(s_type)
        if not fields and not excludes:
            fields = [f[0] for f in optionals]
        return (
            create_schema(
                model=cls,
                name=f"{cls._meta.model_name}Schema{schema_type}",
                fields=fields,
                custom_fields=customs,
                exclude=excludes,
            )
            if fields or customs or excludes
            else None
        )

    @classmethod
    def verbose_name_path_resolver(cls) -> str:
        return "-".join(cls._meta.verbose_name_plural.split(" "))

    def has_changed(self, field: str) -> bool:
        """
        Check if a model field has changed
        """
        if not self.pk:
            return False
        old_value = (
            self.__class__._default_manager.filter(pk=self.pk)
            .values(field)
            .get()[field]
        )
        return getattr(self, field) != old_value

    @classmethod
    async def queryset_request(cls, request: HttpRequest):
        """
        Override this method to return a filtered queryset based
        on the request received
        """
        return cls.objects.select_related().all()

    async def post_create(self) -> None:
        """
        Override this method to execute code after the object
        has been created
        """
        pass

    async def custom_actions(self, payload: dict[str, Any]):
        """
        Override this method to execute custom actions based on
        custom given fields. It could be useful for post create method.
        """
        pass

    @classmethod
    def get_related_schema_data(cls):
        fields = cls.get_fields("read")
        custom_f = {
            name: (value, default)
            for name, value, default in cls.get_custom_fields("read")
        }
        _related_fields = []
        for f in fields + list(custom_f.keys()):
            field_obj = getattr(cls, f)
            if not isinstance(
                field_obj,
                (
                    ManyToManyDescriptor,
                    ReverseManyToOneDescriptor,
                    ReverseOneToOneDescriptor,
                    ForwardManyToOneDescriptor,
                    ForwardOneToOneDescriptor,
                ),
            ):
                _related_fields.append(f)

        if not _related_fields:
            return None, None

        custom_related_fields = [
            (f, *custom_f[f]) for f in _related_fields if f in custom_f
        ]
        related_fields = [f for f in _related_fields if f not in custom_f]
        return related_fields, custom_related_fields

    @classmethod
    def get_schema_out_data(cls):
        fields = []
        reverse_rels = []
        rels = []
        for f in cls.get_fields("read"):
            field_obj = getattr(cls, f)
            if isinstance(
                field_obj,
                (
                    ManyToManyDescriptor,
                    ReverseManyToOneDescriptor,
                    ReverseOneToOneDescriptor,
                ),
            ):
                if isinstance(field_obj, ManyToManyDescriptor):
                    rel_obj: ModelSerializer = field_obj.field.related_model
                    if field_obj.reverse:
                        rel_obj = field_obj.field.model
                    rel_type = "many"
                elif isinstance(field_obj, ReverseManyToOneDescriptor):
                    rel_obj = field_obj.field.model
                    rel_type = "many"
                else:  # ReverseOneToOneDescriptor
                    rel_obj = field_obj.related.related_model
                    rel_type = "one"
                if not isinstance(rel_obj, ModelSerializerMeta):
                    continue
                if not rel_obj.get_fields("read") and not rel_obj.get_custom_fields(
                    "read"
                ):
                    continue
                rel_schema = (
                    rel_obj.generate_related_s()
                    if rel_type != "many"
                    else list[rel_obj.generate_related_s()]
                )
                rel_data = (f, rel_schema | None, None)
                reverse_rels.append(rel_data)
                continue
            if isinstance(
                field_obj, (ForwardOneToOneDescriptor, ForwardManyToOneDescriptor)
            ):
                rel_obj = field_obj.field.related_model
                if not isinstance(rel_obj, ModelSerializerMeta):
                    fields.append(f)
                    continue
                if not rel_obj.get_fields("read") and not rel_obj.get_custom_fields(
                    "read"
                ):
                    continue
                rel_data = (f, rel_obj.generate_related_s() | None, None)
                rels.append(rel_data)
                continue
            fields.append(f)
        return (
            fields,
            reverse_rels,
            cls.get_excluded_fields("read"),
            cls.get_custom_fields("read") + rels,
        )

    @classmethod
    def is_custom(cls, field: str):
        return cls._is_special_field(
            "create", field, "customs"
        ) or cls._is_special_field("update", field, "customs")

    @classmethod
    def is_optional(cls, field: str):
        return cls._is_special_field(
            "create", field, "optionals"
        ) or cls._is_special_field("update", field, "optionals")

    @classmethod
    def get_custom_fields(cls, s_type: type[S_TYPES]) -> list[tuple[str, type, Any]]:
        """
        Normalize declared custom field specs into (name, py_type, default) triples.

        Accepts items shaped as:
          (name, py_type, default) -> kept as-is
          (name, py_type)          -> default filled with Ellipsis (meaning "no default" so required)
        Raises ValueError for any other arity.
        """
        raw_customs = cls._get_fields(s_type, "customs") or []
        normalized: list[tuple[str, type, Any]] = []
        for spec in raw_customs:
            if not isinstance(spec, tuple):
                raise ValueError(f"Custom field spec must be a tuple, got {type(spec)}")
            match len(spec):
                case 3:
                    name, py_type, default = spec
                case 2:
                    name, py_type = spec
                    default = ...
                case _:
                    raise ValueError(
                        f"Custom field tuple must have length 2 or 3 (name, type[, default]); got {len(spec)}"
                    )
            normalized.append((name, py_type, default))
        return normalized

    @classmethod
    def get_optional_fields(cls, s_type: type[S_TYPES]):
        return [
            (field, field_type, None)
            for field, field_type in cls._get_fields(s_type, "optionals")
        ]

    @classmethod
    def get_excluded_fields(cls, s_type: type[S_TYPES]):
        return cls._get_fields(s_type, "excludes")

    @classmethod
    def get_fields(cls, s_type: type[S_TYPES]):
        return cls._get_fields(s_type, "fields")

    @classmethod
    def generate_read_s(cls, depth: int = 1) -> Schema:
        return cls._generate_model_schema("Out", depth)

    @classmethod
    def generate_create_s(cls) -> Schema:
        return cls._generate_model_schema("In")

    @classmethod
    def generate_update_s(cls) -> Schema:
        return cls._generate_model_schema("Patch")

    @classmethod
    def generate_related_s(cls) -> Schema:
        return cls._generate_model_schema("Related")

    def after_save(self):
        """
        Override this method to execute code after the object
        has been saved
        """
        pass

    def before_save(self):
        """
        Override this method to execute code before the object
        has been saved
        """
        pass

    def on_create_after_save(self):
        """
        Override this method to execute code after the object
        has been created
        """
        pass

    def on_create_before_save(self):
        """
        Override this method to execute code before the object
        has been created
        """
        pass

    def on_delete(self):
        """
        Override this method to execute code after the object
        has been deleted
        """
        pass

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.on_create_before_save()
        self.before_save()
        super().save(*args, **kwargs)
        if self._state.adding:
            self.on_create_after_save()
        self.after_save()

    def delete(self, *args, **kwargs):
        res = super().delete(*args, **kwargs)
        self.on_delete()
        return res
