from pydantic import RootModel


class GenericMessageSchema(RootModel[dict[str, str]]):
    root: dict[str, str]
