Model Util class is a NinjaAIO built-in utility class. It gives a lot of utilities for CRUD operations or normal Models operations. Let's give a look on its methods.

## get_object

#### Parameters:

    request: HttpRequest
    pk: int | str

#### Return:

    Model | ModelSerializer

#### Raise:

    SerializerError(error={model_name: 'not found'}, status_code=404)

#### What it does
This method prepares the object query and excutes it asynchronously. If the model is an instance of ModelSerializer it will execute actions defined into **queryset_request** method. It prepares queries also with prefetched relations using Model Util method **get_reverse_relations**, that is usefull to retrieve also the reverse relations and work with them asynchronously.

#### Example

```Python
# views.py
from ninja import Schema
from ninja_aio import NinjaAIO
from ninja_aio.models import ModelUtil
from ninja_aio.views import APIView

from . import models


class FooSchemaOut(Schema):
    id: int
    name: str
    active: bool


class FooRetrieveView(APIView):
    api = api
    api_route_path = "foos/"
    router_tag = "Retrieve Foo"

    def views(self):
        @self.router.get(
            "{id}/",
            response={
                200: schemas.FooSchemaOut,
                self.error_codes: GenericMessageSchema,
            },
        )
        async def retrieve_foo(request: HttpRequest, id: int):
            foo_util = ModelUtil(models.Foo)
            try:
                foo = await foo_util.get_object(request, id)
            except SerializeError as e:
                return e.status_code, e.error
            return 200, foo


FooRetrieveView().add_views_to_route()
```

