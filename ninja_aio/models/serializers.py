from typing import Any, List, Optional, Union, get_args, get_origin, ForwardRef
import warnings
import sys

from django.conf import settings
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
)


class BaseSerializer:
    """
    BaseSerializer
    --------------
    Shared serializer utilities used by both ModelSerializer (model-bound) and
    Serializer (Meta-driven). Centralizes common field normalization, relation
    schema construction and schema generation helpers.

    Subclasses must implement:
    - _get_fields(s_type, f_type): source raw config for fields/optionals/customs/excludes
    - _get_model(): return the Django model class associated with the serializer
    - _get_relations_serializers(): optional mapping of relation field -> serializer (may be empty)
    """

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

    @classmethod
    def _get_fields(cls, s_type: type[S_TYPES], f_type: type[F_TYPES]):
        # Subclasses provide implementation.
        raise NotImplementedError

    @classmethod
    def _get_model(cls) -> models.Model:
        # Subclasses provide implementation.
        raise NotImplementedError

    @classmethod
    def _resolve_string_reference(cls, string_ref: str) -> type:
        """
        Resolve a string serializer reference to an actual class.

        Parameters
        ----------
        string_ref : str
            String reference (local class name or absolute import path).

        Returns
        -------
        type
            The resolved serializer class.

        Raises
        ------
        ValueError
            If the string reference cannot be resolved.
        """
        # Check if it's an absolute import path (contains dots)
        if "." in string_ref:
            # Absolute import path: "myapp.serializers.UserSerializer"
            module_path, class_name = string_ref.rsplit(".", 1)

            try:
                # Try to get or import the module
                module = sys.modules.get(module_path)
                if module is None:
                    import importlib
                    module = importlib.import_module(module_path)

                # Get the serializer class from the module
                serializer_class = getattr(module, class_name, None)

                if serializer_class is None:
                    raise ValueError(
                        f"Cannot resolve serializer reference '{string_ref}': "
                        f"class '{class_name}' not found in module '{module_path}'."
                    )

                return serializer_class
            except ImportError as e:
                raise ValueError(
                    f"Cannot resolve serializer reference '{string_ref}': "
                    f"failed to import module '{module_path}': {e}"
                )

        # Local reference: simple class name in the same module
        module = sys.modules.get(cls.__module__)

        if module is None:
            raise ValueError(
                f"Cannot resolve serializer reference '{string_ref}': "
                f"module '{cls.__module__}' not found in sys.modules."
            )

        serializer_class = getattr(module, string_ref, None)

        if serializer_class is None:
            raise ValueError(
                f"Cannot resolve serializer reference '{string_ref}' in module '{cls.__module__}'. "
                f"Make sure the serializer class '{string_ref}' is defined in the same module as {cls.__name__}."
            )

        return serializer_class

    @classmethod
    def _resolve_serializer_reference(cls, serializer_ref: str | type | Any) -> type | Any:
        """
        Resolve a serializer reference that may be a string, a class, or a Union of serializers.

        This method performs lazy resolution, meaning it will attempt to resolve
        string references only when called, allowing for forward references and
        circular dependencies between serializers in the same module.

        Parameters
        ----------
        serializer_ref : str | type | Union
            Either a string reference to a serializer class, an actual serializer class,
            or a Union of serializer references. String references can be:
            - A class name in the same module (e.g., "UserSerializer")
            - An absolute import path (e.g., "myapp.serializers.UserSerializer")

        Returns
        -------
        type | Union
            The resolved serializer class or Union of serializer classes.

        Raises
        ------
        ValueError
            If the string reference cannot be resolved.

        Examples
        --------
        >>> # Single reference
        >>> cls._resolve_serializer_reference("UserSerializer")
        >>> cls._resolve_serializer_reference(UserSerializer)
        >>>
        >>> # Union reference
        >>> from typing import Union
        >>> cls._resolve_serializer_reference(Union[UserSerializer, AdminSerializer])
        >>> cls._resolve_serializer_reference(Union["UserSerializer", "AdminSerializer"])
        """
        # Handle Union types
        origin = get_origin(serializer_ref)
        if origin is Union:
            resolved_types = tuple(
                cls._resolve_serializer_reference(arg)
                for arg in get_args(serializer_ref)
            )
            # Optimize single-type unions
            if len(resolved_types) == 1:
                return resolved_types[0]
            # Create Union using indexing syntax for Python 3.10+ compatibility
            return Union[resolved_types]

        # Handle ForwardRef (created when using Union["StringType"])
        if isinstance(serializer_ref, ForwardRef):
            return cls._resolve_serializer_reference(serializer_ref.__forward_arg__)

        # Handle string references
        if isinstance(serializer_ref, str):
            return cls._resolve_string_reference(serializer_ref)

        # Already a class, return as-is
        return serializer_ref

    @classmethod
    def _get_relations_serializers(cls) -> dict[str, "Serializer"]:
        # Optional in subclasses. Default to no explicit relation serializers.
        return {}

    @classmethod
    def _generate_union_schema(cls, resolved_union: Any) -> Any:
        """
        Generate a Union schema from multiple resolved serializers.

        Parameters
        ----------
        resolved_union : Union
            A Union type containing resolved serializer classes.

        Returns
        -------
        Schema | Union[Schema, ...] | None
            Union of generated schemas or None if all schemas are None.
        """
        # Generate schemas for each serializer in the Union
        schemas = tuple(
            serializer_type.generate_related_s()
            for serializer_type in get_args(resolved_union)
            if serializer_type.generate_related_s() is not None
        )

        if not schemas:
            return None

        # Optimize single-schema unions
        if len(schemas) == 1:
            return schemas[0]

        # Create Union of schemas using indexing syntax for Python 3.10+ compatibility
        return Union[schemas]

    @classmethod
    def _resolve_relation_schema(cls, field_name: str, rel_model: models.Model):
        """
        Resolve and generate schema for a related model.

        Parameters
        ----------
        field_name : str
            Name of the relation field.
        rel_model : models.Model
            The related model class.

        Returns
        -------
        Schema | Union[Schema, ...] | None
            Generated schema, Union of schemas, or None if cannot be resolved.
        """
        # Auto-resolve ModelSerializer with readable fields
        if isinstance(rel_model, ModelSerializerMeta):
            if rel_model.get_fields("read") or rel_model.get_custom_fields("read"):
                return rel_model.generate_related_s()
            return None

        # Resolve from explicit serializer mapping
        rel_serializers = cls._get_relations_serializers() or {}
        serializer_ref = rel_serializers.get(field_name)

        if not serializer_ref:
            return None

        resolved = cls._resolve_serializer_reference(serializer_ref)

        # Handle Union of serializers
        if get_origin(resolved) is Union:
            return cls._generate_union_schema(resolved)

        # Handle single serializer
        return resolved.generate_related_s()

    @classmethod
    def _is_special_field(
        cls, s_type: type[S_TYPES], field: str, f_type: type[F_TYPES]
    ) -> bool:
        """Return True if field appears in the given category for s_type."""
        special_fields = cls._get_fields(s_type, f_type)
        return any(field in special_f for special_f in special_fields)

    @classmethod
    def get_custom_fields(cls, s_type: type[S_TYPES]) -> list[tuple[str, type, Any]]:
        """
        Normalize declared custom field specs into (name, py_type, default).
        Accepted tuple shapes:
        - (name, py_type, default)
        - (name, py_type) -> default Ellipsis (required)
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
        """Return optional field specs normalized to (name, type, None)."""
        return [
            (field, field_type, None)
            for field, field_type in cls._get_fields(s_type, "optionals")
        ]

    @classmethod
    def get_excluded_fields(cls, s_type: type[S_TYPES]):
        """Return excluded field names for the serializer type."""
        return cls._get_fields(s_type, "excludes")

    @classmethod
    def get_fields(cls, s_type: type[S_TYPES]):
        """Return explicit declared fields for the serializer type."""
        return cls._get_fields(s_type, "fields")

    @classmethod
    def is_custom(cls, field: str) -> bool:
        """True if field is declared as a custom input in create or update."""
        return cls._is_special_field(
            "create", field, "customs"
        ) or cls._is_special_field("update", field, "customs")

    @classmethod
    def is_optional(cls, field: str) -> bool:
        """True if field is declared as optional in create or update."""
        return cls._is_special_field(
            "create", field, "optionals"
        ) or cls._is_special_field("update", field, "optionals")

    @classmethod
    def _build_schema_reverse_rel(cls, field_name: str, descriptor: Any):
        """
        Build a reverse relation schema component for 'Out' schema generation.
        Returns a custom field tuple or None to skip.
        """
        # Resolve related model and cardinality
        if isinstance(descriptor, ManyToManyDescriptor):
            # M2M uses the same descriptor on both sides; rely on .reverse to pick the model
            rel_model: models.Model = (
                descriptor.field.model
                if descriptor.reverse
                else descriptor.field.related_model
            )
            many = True
        elif isinstance(descriptor, ReverseManyToOneDescriptor):
            rel_model = descriptor.field.model
            many = True
        else:  # ReverseOneToOneDescriptor
            rel_model = descriptor.related.related_model
            many = False

        schema = cls._resolve_relation_schema(field_name, rel_model)
        if not schema:
            return None

        rel_schema_type = schema if not many else list[schema]
        return (field_name, rel_schema_type | None, None)

    @classmethod
    def _build_schema_forward_rel(cls, field_name: str, descriptor: Any):
        """
        Build a forward relation schema component for 'Out' schema generation.
        Returns True to treat as plain field, a custom field tuple to include relation schema,
        or None to skip entirely.
        """
        rel_model = descriptor.field.related_model

        # Special case: ModelSerializer with no readable fields should be skipped entirely
        if isinstance(rel_model, ModelSerializerMeta):
            if not (
                rel_model.get_fields("read") or rel_model.get_custom_fields("read")
            ):
                return None

        schema = cls._resolve_relation_schema(field_name, rel_model)
        if not schema:
            # Could not build a schema: treat as a plain field (serialize as-is)
            return True

        # Forward relations are single objects; allow nullability
        return (field_name, schema | None, None)

    @classmethod
    def get_schema_out_data(cls):
        """
        Collect components for 'Out' read schema generation.
        Returns (fields, reverse_rel_descriptors, excludes, custom_fields_with_forward_relations, optionals).
        Enforces relation serializers only when provided by subclass via _get_relations_serializers.
        """
        fields: list[str] = []
        reverse_rels: list[tuple] = []
        rels: list[tuple] = []
        relations_serializers = cls._get_relations_serializers() or {}
        model = cls._get_model()

        for f in cls.get_fields("read"):
            field_obj = getattr(model, f)
            is_reverse = isinstance(
                field_obj,
                (
                    ManyToManyDescriptor,
                    ReverseManyToOneDescriptor,
                    ReverseOneToOneDescriptor,
                ),
            )
            is_forward = isinstance(
                field_obj, (ForwardOneToOneDescriptor, ForwardManyToOneDescriptor)
            )

            # If explicit relation serializers are declared, require mapping presence.
            if (
                is_reverse
                and not isinstance(model, ModelSerializerMeta)
                and f not in relations_serializers
                and not getattr(settings, "NINJA_AIO_TESTING", False)
            ):
                warnings.warn(
                    f"{cls.__name__}: reverse relation '{f}' is listed in read fields but has no entry in relations_serializers; "
                    "it will be auto-resolved only for ModelSerializer relations, otherwise skipped.",
                    UserWarning,
                    stacklevel=2,
                )

            # Reverse relations
            if is_reverse:
                rel_tuple = cls._build_schema_reverse_rel(f, field_obj)
                if rel_tuple:
                    reverse_rels.append(rel_tuple)
                continue

            # Forward relations
            if is_forward:
                rel_tuple = cls._build_schema_forward_rel(f, field_obj)
                if rel_tuple is True:
                    fields.append(f)
                elif rel_tuple:
                    rels.append(rel_tuple)
                # None -> skip entirely
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
    def _generate_model_schema(
        cls,
        schema_type: type[SCHEMA_TYPES],
        depth: int = None,
    ) -> Schema:
        """
        Core schema factory bridging configuration to ninja.orm.create_schema.
        Handles In/Patch/Out/Related.
        """
        model = cls._get_model()

        # Handle special schema types with custom logic
        if schema_type == "Out":
            fields, reverse_rels, excludes, customs, optionals = (
                cls.get_schema_out_data()
            )
            if not any([fields, reverse_rels, excludes, customs]):
                return None
            return create_schema(
                model=model,
                name=f"{model._meta.model_name}SchemaOut",
                depth=depth,
                fields=fields,
                custom_fields=reverse_rels + customs + optionals,
                exclude=excludes,
            )

        if schema_type == "Related":
            fields, customs = cls.get_related_schema_data()
            if not fields and not customs:
                return None
            return create_schema(
                model=model,
                name=f"{model._meta.model_name}SchemaRelated",
                fields=fields,
                custom_fields=customs,
            )

        # Handle standard In/Patch schema types
        s_type = "create" if schema_type == "In" else "update"
        fields = cls.get_fields(s_type)
        optionals = cls.get_optional_fields(s_type)
        customs = cls.get_custom_fields(s_type) + optionals
        excludes = cls.get_excluded_fields(s_type)

        # If no explicit fields but have optionals, use optional field names as fields
        if not fields and not excludes:
            fields = [f[0] for f in optionals]

        # Only create schema if we have something to include
        if not any([fields, customs, excludes]):
            return None

        return create_schema(
            model=model,
            name=f"{model._meta.model_name}Schema{schema_type}",
            fields=fields,
            custom_fields=customs,
            exclude=excludes,
        )

    @classmethod
    def get_related_schema_data(cls):
        """
        Build field/custom lists for 'Related' schema, flattening non-relational fields.
        """
        fields = cls.get_fields("read")
        custom_f = {
            name: (value, default)
            for name, value, default in cls.get_custom_fields("read")
        }
        _related_fields = []
        model = cls._get_model()
        for f in fields + list(custom_f.keys()):
            field_obj = getattr(model, f)
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
    def generate_read_s(cls, depth: int = 1) -> Schema:
        """Generate read (Out) schema."""
        return cls._generate_model_schema("Out", depth)

    @classmethod
    def generate_create_s(cls) -> Schema:
        """Generate create (In) schema."""
        return cls._generate_model_schema("In")

    @classmethod
    def generate_update_s(cls) -> Schema:
        """Generate update (Patch) schema."""
        return cls._generate_model_schema("Patch")

    @classmethod
    def generate_related_s(cls) -> Schema:
        """Generate related (nested) schema."""
        return cls._generate_model_schema("Related")

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
        raise NotImplementedError


class ModelSerializer(models.Model, BaseSerializer, metaclass=ModelSerializerMeta):
    """
    ModelSerializer
    =================
    Model-bound serializer mixin centralizing declarative configuration directly
    on the model class. Inherits common behavior from BaseSerializer and adds
    lifecycle hooks and query utilities.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from ninja_aio.models.utils import ModelUtil
        from ninja_aio.helpers.query import QueryUtil

        # Bind a ModelUtil instance to the subclass for convenient access
        cls.util = ModelUtil(cls)
        cls.query_util = QueryUtil(cls)

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

    # Serializer type to configuration class mapping
    _SERIALIZER_CONFIG_MAP = {
        "create": "CreateSerializer",
        "update": "UpdateSerializer",
        "read": "ReadSerializer",
    }

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
        config_class_name = cls._SERIALIZER_CONFIG_MAP.get(s_type)
        if not config_class_name:
            return []
        config_class = getattr(cls, config_class_name)
        return getattr(config_class, f_type, [])

    @classmethod
    def _get_model(cls) -> "ModelSerializer":
        """Return the model class itself."""
        return cls

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


class SchemaModelConfig(Schema):
    """
    SchemaModelConfig
    -----------------
    Configuration container for declarative schema definitions.
    Attributes
    ----------
    fields : Optional[List[str]]
        Explicit model fields to include.
    optionals : Optional[List[tuple[str, type]]]
        Optional model fields.
    exclude : Optional[List[str]]
        Model fields to exclude.
    customs : Optional[List[tuple[str, type, Any]]]
        Custom / synthetic fields.
    """

    fields: Optional[List[str]] = None
    optionals: Optional[List[tuple[str, type]]] = None
    exclude: Optional[List[str]] = None
    customs: Optional[List[tuple[str, type, Any]]] = None


class Serializer(BaseSerializer):
    """
    Serializer
    ----------
    Meta-driven serializer for arbitrary Django models. Shares common behavior
    from BaseSerializer but sources configuration from the nested Meta class.
    Supports optional relations_serializers mapping to explicitly include related
    schema components during read schema generation.
    """

    # Serializer type to Meta schema attribute mapping
    _SCHEMA_META_MAP = {
        "create": "in",
        "update": "update",
        "read": "out",
    }

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from ninja_aio.models.utils import ModelUtil
        from ninja_aio.helpers.query import QueryUtil

        cls.model = cls._get_model()
        cls.util = ModelUtil(cls.model, serializer_class=cls)
        cls.query_util = QueryUtil(cls)
        cls._meta = cls.Meta

    class Meta:
        model: models.Model = None
        schema_in: Optional[SchemaModelConfig] = None
        schema_out: Optional[SchemaModelConfig] = None
        schema_update: Optional[SchemaModelConfig] = None
        relations_serializers: dict[str, "Serializer"] = {}

    @classmethod
    def _get_meta_data(cls, attr_name: str) -> Any:
        return getattr(cls.Meta, attr_name, None)

    @classmethod
    def _get_model(cls) -> models.Model:
        return cls._validate_model()

    @classmethod
    def _get_relations_serializers(cls) -> dict[str, "Serializer"]:
        relations_serializers = cls._get_meta_data("relations_serializers")
        return relations_serializers or {}

    @classmethod
    def _get_schema_meta(cls, schema_type: str) -> SchemaModelConfig | None:
        match schema_type:
            case "in":
                return cls._get_meta_data("schema_in")
            case "out":
                return cls._get_meta_data("schema_out")
            case "update":
                return cls._get_meta_data("schema_update")
            case _:
                return None

    @classmethod
    def _validate_model(cls):
        model = cls._get_meta_data("model")
        if not model:
            raise ValueError("Meta.model must be defined for Serializer.")
        if not issubclass(model, models.Model):
            raise ValueError("Meta.model must be a Django model")
        return model

    @classmethod
    def _get_fields(cls, s_type: type[S_TYPES], f_type: type[F_TYPES]):
        """Internal accessor for raw configuration lists from Meta schemas."""
        schema_key = cls._SCHEMA_META_MAP.get(s_type)
        if not schema_key:
            return []
        schema = cls._get_schema_meta(schema_key)
        if not schema:
            return []
        return getattr(schema, f_type, []) or []

    @classmethod
    async def queryset_request(cls, request: HttpRequest):
        return cls.query_util.apply_queryset_optimizations(
            queryset=cls.model._default_manager.all(),
            scope=cls.query_util.SCOPES.QUERYSET_REQUEST,
        )

    async def post_create(self, instance: models.Model) -> None:
        """
        Async hook executed after first persistence (create path).
        """
        pass

    async def custom_actions(self, payload: dict[str, Any], instance: models.Model):
        """
        Async hook for reacting to provided custom (synthetic) fields.

        Parameters
        ----------
        payload : dict
            Custom field name/value pairs.
        """
        pass

    async def save(self, instance: models.Model) -> models.Model:
        """
        Async helper to save a model instance with lifecycle hooks.

        Parameters
        ----------
        instance : models.Model
            The model instance to save.
        """
        creation = instance._state.adding
        if creation:
            self.on_create_before_save(instance)
        self.before_save(instance)
        await instance.asave()
        if creation:
            self.on_create_after_save(instance)
        self.after_save(instance)
        return instance

    async def create(self, payload: dict[str, Any]) -> models.Model:
        """
        Create a new model instance from the provided payload.

        Parameters
        ----------
        payload : dict
            Input data.

        Returns
        -------
        models.Model
            Created model instance.
        """
        instance: models.Model = self.model(**payload)
        return await self.save(instance)

    async def update(
        self, instance: models.Model, payload: dict[str, Any]
    ) -> models.Model:
        """
        Update an existing model instance with the provided payload.

        Parameters
        ----------
        instance : models.Model
            The model instance to update.
        payload : dict
            Input data.

        Returns
        -------
        models.Model
            Updated model instance.
        """
        for attr, value in payload.items():
            setattr(instance, attr, value)
        return await self.save(instance)

    async def model_dump(self, instance: models.Model) -> dict[str, Any]:
        """
        Serialize a model instance to a dictionary using the Out schema.

        Parameters
        ----------
        instance : models.Model
            The model instance to serialize.

        Returns
        -------
        dict
            Serialized data.
        """
        return await self.util.read_s(schema=self.generate_read_s(), instance=instance)

    async def models_dump(
        self, instances: models.QuerySet[models.Model]
    ) -> list[dict[str, Any]]:
        """
        Serialize a list of model instances to a list of dictionaries using the Out schema.

        Parameters
        ----------
        instances : list[models.Model]
            The list of model instances to serialize.

        Returns
        -------
        list[dict]
            List of serialized data.
        """
        return await self.util.list_read_s(
            schema=self.generate_read_s(), instances=instances
        )

    def after_save(self, instance: models.Model):
        """
        Sync hook executed after any save (create or update).
        """
        pass

    def before_save(self, instance: models.Model):
        """
        Sync hook executed before any save (create or update).
        """
        pass

    def on_create_after_save(self, instance: models.Model):
        """
        Sync hook executed only after initial creation save.
        """
        pass

    def on_create_before_save(self, instance: models.Model):
        """
        Sync hook executed only before initial creation save.
        """
        pass

    def on_delete(self, instance: models.Model):
        """
        Sync hook executed after delete.
        """
        pass
