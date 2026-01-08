from typing import Any, ClassVar

from ninja import Schema
from ninja.orm import create_schema
from django.db import models
from django.http import HttpRequest
from django.db.models.fields.related_descriptors import (
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    ManyToManyDescriptor,
    ForwardManyToOneDescriptor,
    ForwardOneToOneDescriptor,
)

from ninja_aio.types import S_TYPES, F_TYPES, SCHEMA_TYPES, ModelSerializerMeta
from ninja_aio.schemas.helpers import (
    ModelQuerySetSchema,
    ModelQuerySetExtraSchema,
    SerializerSchema,
)
from ninja_aio.helpers.query import QueryUtil


class ModelSerializer(models.Model, metaclass=ModelSerializerMeta):
    """
    ModelSerializer
    =================
    Abstract mixin for Django models centralizing (on the model class itself) the
    declarative configuration required to auto-generate create / update / read /
    related schemas.

    Goals
    -----
    - Remove duplication between Model and separate serializer classes.
    - Provide clear extension points (sync + async hooks, custom synthetic fields).

    See inline docstrings for per-method behavior.
    """

    util: ClassVar
    query_util: ClassVar[QueryUtil]

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        from ninja_aio.models.utils import ModelUtil

        # Bind a ModelUtil instance to the subclass for convenient access
        cls.util = ModelUtil(cls)
        cls.query_util = QueryUtil(cls)

    class QuerySet:
        """
        Configuration container describing how to build query schemas for a model.
        Purpose
        -------
        Describes which fields and extras are available when querying for model
        instances. A factory/metaclass can read this configuration to generate
        Pydantic / Ninja query schemas.
        Attributes
        ----------
        read : ModelQuerySetSchema
            Schema configuration for read operations.
        queryset_request : ModelQuerySetSchema
            Schema configuration for queryset_request hook.
        extras : list[ModelQuerySetExtraSchema]
            Additional computed / synthetic query parameters.
        """

        read = ModelQuerySetSchema()
        queryset_request = ModelQuerySetSchema()
        extras: list[ModelQuerySetExtraSchema] = []

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
            REQUIRED model fields.
        optionals : list[tuple[str, type]]
            Optional model fields (nullable / patch-like).
        customs : list[tuple[str, type, Any]]
            Synthetic input fields (non-model).
        excludes : list[str]
            Disallowed model fields on create (e.g., id, timestamps).
        """

        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []
        optionals: list[tuple[str, type]] = []
        excludes: list[str] = []

    class ReadSerializer:
        """Configuration describing how to build a read (output) schema.

        Attributes
        ----------
        fields : list[str]
            Explicit model fields to include.
        excludes : list[str]
            Fields to force exclude (safety).
        customs : list[tuple[str, type, Any]]
            Computed / synthetic output attributes.
        optionals : list[tuple[str, type]]
            Optional output fields.
        """

        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []
        optionals: list[tuple[str, type]] = []
        excludes: list[str] = []

    class UpdateSerializer:
        """Configuration describing update (PATCH/PUT) schema.

        Attributes
        ----------
        fields : list[str]
            Required update fields (rare).
        optionals : list[tuple[str, type]]
            Editable optional fields.
        customs : list[tuple[str, type, Any]]
            Synthetic operational inputs.
        excludes : list[str]
            Immutable / blocked fields.
        """

        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []
        optionals: list[tuple[str, type]] = []
        excludes: list[str] = []

    @classmethod
    def _get_fields(cls, s_type: type[S_TYPES], f_type: type[F_TYPES]):
        """
        Internal accessor for raw configuration lists.

        Parameters
        ----------
        s_type : str
            Serializer type ("create" | "update" | "read").
        f_type : str
            Field category ("fields" | "optionals" | "customs" | "excludes").

        Returns
        -------
        list
            Raw configuration list or empty list.
        """
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
        """
        Determine if a field is declared in a given category for a serializer type.

        Parameters
        ----------
        s_type : str
        field : str
        f_type : str

        Returns
        -------
        bool
        """
        special_fields = cls._get_fields(s_type, f_type)
        return any(field in special_f for special_f in special_fields)

    @classmethod
    def _generate_model_schema(
        cls,
        schema_type: type[SCHEMA_TYPES],
        depth: int = None,
    ) -> Schema:
        """
        Core schema factory bridging configuration and ninja.orm.create_schema.

        Parameters
        ----------
        schema_type : str
            "In" | "Patch" | "Out" | "Related".
        depth : int, optional
            Relation depth for read schema.

        Returns
        -------
        Schema | None
            Generated schema class or None if no fields.
        """
        match schema_type:
            case "In":
                s_type = "create"
            case "Patch":
                s_type = "update"
            case "Out":
                fields, reverse_rels, excludes, customs, optionals = (
                    cls.get_schema_out_data()
                )
                if not fields and not reverse_rels and not excludes and not customs:
                    return None
                return create_schema(
                    model=cls,
                    name=f"{cls._meta.model_name}SchemaOut",
                    depth=depth,
                    fields=fields,
                    custom_fields=reverse_rels + customs + optionals,
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
        """
        Slugify plural verbose name for URL path segment.

        Returns
        -------
        str
        """
        return "-".join(cls._meta.verbose_name_plural.split(" "))

    def has_changed(self, field: str) -> bool:
        """
        Check if a model field has changed compared to the persisted value.

        Parameters
        ----------
        field : str
            Field name.

        Returns
        -------
        bool
            True if in-memory value differs from DB value.
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
        Override to return a request-scoped filtered queryset.

        Parameters
        ----------
        request : HttpRequest

        Returns
        -------
        QuerySet
        """
        return cls.query_util.apply_queryset_optimizations(
            queryset=cls.objects.all(),
            scope=cls.query_util.SCOPES.QUERYSET_REQUEST,
        )

    async def post_create(self) -> None:
        """
        Async hook executed after first persistence (create path).
        """
        pass

    async def custom_actions(self, payload: dict[str, Any]):
        """
        Async hook for reacting to provided custom (synthetic) fields.

        Parameters
        ----------
        payload : dict
            Custom field name/value pairs.
        """
        pass

    @classmethod
    def get_related_schema_data(cls):
        """
        Build field/custom lists for 'Related' schema (flattening non-relational fields).

        Returns
        -------
        tuple[list[str] | None, list[tuple] | None]
            (related_fields, custom_related_fields) or (None, None)
        """
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
    def _build_schema_reverse_rel(cls, field_name: str, descriptor: Any):
        """
        Build a reverse relation schema component for 'Out' schema generation.
        """
        if isinstance(descriptor, ManyToManyDescriptor):
            rel_model: ModelSerializer = descriptor.field.related_model
            if descriptor.reverse:  # reverse side of M2M
                rel_model = descriptor.field.model
            rel_type = "many"
        elif isinstance(descriptor, ReverseManyToOneDescriptor):
            rel_model = descriptor.field.model
            rel_type = "many"
        else:  # ReverseOneToOneDescriptor
            rel_model = descriptor.related.related_model
            rel_type = "one"

        if not isinstance(rel_model, ModelSerializerMeta):
            return None
        if not rel_model.get_fields("read") and not rel_model.get_custom_fields("read"):
            return None

        rel_schema = (
            rel_model.generate_related_s()
            if rel_type == "one"
            else list[rel_model.generate_related_s()]
        )
        return (field_name, rel_schema | None, None)

    @classmethod
    def _build_schema_forward_rel(cls, field_name: str, descriptor: Any):
        """
        Build a forward relation schema component for 'Out' schema generation.
        """
        rel_model = descriptor.field.related_model
        if not isinstance(rel_model, ModelSerializerMeta):
            return True  # Signal: treat as plain field
        if not rel_model.get_fields("read") and not rel_model.get_custom_fields("read"):
            return None  # Skip entirely
        rel_schema = rel_model.generate_related_s()
        return (field_name, rel_schema | None, None)

    @classmethod
    def get_schema_out_data(cls):
        """
        Collect components for 'Out' read schema generation.

        Returns
        -------
        tuple
            (fields, reverse_rel_descriptors, excludes, custom_fields_with_forward_relations)
        """

        fields: list[str] = []
        reverse_rels: list[tuple] = []
        rels: list[tuple] = []

        for f in cls.get_fields("read"):
            field_obj = getattr(cls, f)

            # Reverse relations
            if isinstance(
                field_obj,
                (
                    ManyToManyDescriptor,
                    ReverseManyToOneDescriptor,
                    ReverseOneToOneDescriptor,
                ),
            ):
                rel_tuple = cls._build_schema_reverse_rel(f, field_obj)
                if rel_tuple:
                    reverse_rels.append(rel_tuple)
                    continue

            # Forward relations
            if isinstance(
                field_obj, (ForwardOneToOneDescriptor, ForwardManyToOneDescriptor)
            ):
                rel_tuple = cls._build_schema_forward_rel(f, field_obj)
                if rel_tuple is True:
                    fields.append(f)
                elif rel_tuple:
                    rels.append(rel_tuple)
                # If rel_tuple is None -> skip
                continue

            # Plain field
            fields.append(f)

        return (
            fields,
            reverse_rels,
            cls.get_excluded_fields("read"),
            cls.get_custom_fields("read") + rels,
            cls.get_optional_fields("read"),
        )

    @classmethod
    def is_custom(cls, field: str):
        """
        Check if a field is declared as a custom input (create or update).

        Parameters
        ----------
        field : str

        Returns
        -------
        bool
        """
        return cls._is_special_field(
            "create", field, "customs"
        ) or cls._is_special_field("update", field, "customs")

    @classmethod
    def is_optional(cls, field: str):
        """
        Check if a field is declared as optional (create or update).

        Parameters
        ----------
        field : str

        Returns
        -------
        bool
        """
        return cls._is_special_field(
            "create", field, "optionals"
        ) or cls._is_special_field("update", field, "optionals")

    @classmethod
    def get_custom_fields(cls, s_type: type[S_TYPES]) -> list[tuple[str, type, Any]]:
        """
        Normalize declared custom field specs into (name, py_type, default) triples.

        Accepted tuple shapes:
          (name, py_type, default) -> keeps provided default (callable or literal)
          (name, py_type)          -> marks as required (default = Ellipsis)
        Any other arity raises ValueError.

        Parameters
        ----------
        s_type : str
            "create" | "update" | "read"

        Returns
        -------
        list[tuple[str, type, Any]]
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
        """
        Return optional field specifications normalized to (name, type, None).

        Parameters
        ----------
        s_type : str

        Returns
        -------
        list[tuple[str, type, None]]
        """
        return [
            (field, field_type, None)
            for field, field_type in cls._get_fields(s_type, "optionals")
        ]

    @classmethod
    def get_excluded_fields(cls, s_type: type[S_TYPES]):
        """
        Return excluded field names for a serializer type.

        Parameters
        ----------
        s_type : str

        Returns
        -------
        list[str]
        """
        return cls._get_fields(s_type, "excludes")

    @classmethod
    def get_fields(cls, s_type: type[S_TYPES]):
        """
        Return explicit declared fields for a serializer type.

        Parameters
        ----------
        s_type : str

        Returns
        -------
        list[str]
        """
        return cls._get_fields(s_type, "fields")

    @classmethod
    def generate_read_s(cls, depth: int = 1) -> Schema:
        """
        Generate read (Out) schema.

        Parameters
        ----------
        depth : int
            Relation depth.

        Returns
        -------
        Schema | None
        """
        return cls._generate_model_schema("Out", depth)

    @classmethod
    def generate_create_s(cls) -> Schema:
        """
        Generate create (In) schema.

        Returns
        -------
        Schema | None
        """
        return cls._generate_model_schema("In")

    @classmethod
    def generate_update_s(cls) -> Schema:
        """
        Generate update (Patch) schema.

        Returns
        -------
        Schema | None
        """
        return cls._generate_model_schema("Patch")

    @classmethod
    def generate_related_s(cls) -> Schema:
        """
        Generate related (nested) schema.

        Returns
        -------
        Schema | None
        """
        return cls._generate_model_schema("Related")

    def after_save(self):
        """
        Sync hook executed after any save (create or update).
        """
        pass

    def before_save(self):
        """
        Sync hook executed before any save (create or update).
        """
        pass

    def on_create_after_save(self):
        """
        Sync hook executed only after initial creation save.
        """
        pass

    def on_create_before_save(self):
        """
        Sync hook executed only before initial creation save.
        """
        pass

    def on_delete(self):
        """
        Sync hook executed after delete.
        """
        pass

    def save(self, *args, **kwargs):
        """
        Override save lifecycle to inject create/update hooks.
        """
        state_adding = self._state.adding
        if state_adding:
            self.on_create_before_save()
        self.before_save()
        super().save(*args, **kwargs)
        if state_adding:
            self.on_create_after_save()
        self.after_save()

    def delete(self, *args, **kwargs):
        """
        Override delete to inject on_delete hook.

        Returns
        -------
        tuple(int, dict)
            Django delete return signature.
        """
        res = super().delete(*args, **kwargs)
        self.on_delete()
        return res


class Serializer:
    class Meta:
        model: type[ModelSerializer] | models.Model = None
        schema_in: SerializerSchema = None
        schema_out: SerializerSchema = None
        schema_update: SerializerSchema = None

    def __init__(self):
        self.model = self._validate_model()

    @classmethod
    def _get_meta_data(cls, attr_name: str) -> Any:
        return getattr(cls.Meta, attr_name, None)

    @classmethod
    def _generate_schema(cls, schema_meta: SerializerSchema, name: str) -> Schema:
        fields = schema_meta.fields or []
        optionals = [
            (field, field_type, None)
            for field, field_type in (schema_meta.optionals or [])
        ]
        customs = schema_meta.customs or []
        excludes = schema_meta.exclude or []
        if not fields and not excludes and not customs and not optionals:
            return None
        return create_schema(
            model=cls.model,
            name=name,
            fields=fields,
            custom_fields=customs + optionals,
            exclude=excludes,
        )

    def _validate_model(self):
        model = self._get_meta_data("model")
        if not model:
            raise ValueError("Meta.model must be defined for Serializer.")
        if not issubclass(model, (models.Model, ModelSerializerMeta)):
            raise ValueError("Meta.model must be a Django model or ModelSerializer.")
        return model
