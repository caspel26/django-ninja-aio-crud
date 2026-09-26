from django.core import checks
from django.core.exceptions import FieldDoesNotExist

from ninja_aio.models.config import CONFIG_KINDS, SchemaConfig
from ninja_aio.types import ModelSerializerMeta

_RELATION_ONLY_KINDS = ("read", "detail")


def _find_field(model, name):
    try:
        return model._meta.get_field(name)
    except FieldDoesNotExist:
        return next(
            (r for r in model._meta.related_objects if r.get_accessor_name() == name),
            None,
        )


def _referenced_names(config: SchemaConfig) -> list[str]:
    return [
        *(name for name in config.fields if isinstance(name, str)),
        *(optional[0] for optional in config.optionals),
        *config.excludes,
        *config.relations_as_id,
        *config.nested,
    ]


def _config_errors(serializer, model, kind: str, config: SchemaConfig) -> list[checks.CheckMessage]:
    label = f"{serializer.__name__}.Schemas.{kind}"
    errors = [
        checks.Error(
            f"{label} references unknown field '{name}' on {model.__name__}.",
            hint="Use a model field, relation accessor, or declare it in customs.",
            obj=serializer,
            id="ninja_aio.E003",
        )
        for name in dict.fromkeys(_referenced_names(config))
        if not hasattr(model, name)
    ]
    field_names = {name for name in config.fields if isinstance(name, str)}
    errors += [
        checks.Error(
            f"{label} lists '{optional[0]}' in both fields and optionals.",
            obj=serializer,
            id="ninja_aio.E004",
        )
        for optional in config.optionals
        if optional[0] in field_names
    ]
    if config.relations_as_id and kind not in _RELATION_ONLY_KINDS:
        errors.append(
            checks.Error(
                f"{label} sets relations_as_id, which only applies to read and detail.",
                obj=serializer,
                id="ninja_aio.E005",
            )
        )
    if config.nested and (kind != "create" or not isinstance(serializer, ModelSerializerMeta)):
        errors.append(
            checks.Error(
                f"{label} sets nested, which only applies to ModelSerializer create schemas.",
                obj=serializer,
                id="ninja_aio.E005",
            )
        )
    for name in config.relations_as_id:
        field = _find_field(model, name)
        if field is not None and not field.is_relation:
            errors.append(
                checks.Error(
                    f"{label} lists '{name}' in relations_as_id, but it is not a relation.",
                    obj=serializer,
                    id="ninja_aio.E006",
                )
            )
    return errors


def _schemas_errors(serializer, model, schemas) -> list[checks.CheckMessage]:
    errors = []
    for name, config in vars(schemas).items():
        if name.startswith("_"):
            continue
        if name not in CONFIG_KINDS:
            errors.append(
                checks.Error(
                    f"{serializer.__name__}.Schemas.{name} is not a schema kind.",
                    hint=f"Use one of: {', '.join(CONFIG_KINDS)}.",
                    obj=serializer,
                    id="ninja_aio.E001",
                )
            )
        elif not isinstance(config, SchemaConfig):
            errors.append(
                checks.Error(
                    f"{serializer.__name__}.Schemas.{name} must be a SchemaConfig.",
                    obj=serializer,
                    id="ninja_aio.E002",
                )
            )
        else:
            errors += _config_errors(serializer, model, name, config)
    return errors


@checks.register()
def check_serializer_schemas(app_configs=None, **kwargs) -> list[checks.CheckMessage]:
    """Validate every serializer's ``Schemas`` declaration against its model."""
    # Imported here: serializers define models, which need a ready app registry.
    from ninja_aio.models.serializers import SERIALIZER_CLASSES

    errors = []
    for serializer in list(SERIALIZER_CLASSES):
        schemas = getattr(serializer, "Schemas", None)
        model = serializer._get_model()
        if schemas is None or model._meta.abstract:
            continue
        if app_configs is not None and model._meta.app_config not in app_configs:
            continue
        errors += _schemas_errors(serializer, model, schemas)
    return errors
