# 🥷 NinjaAioCRUD

## 📝 Instructions

### 📚 Prerequisites
- Install Python from the [official website](https://www.python.org/) (latest version) and ensure it is added to the system Path and environment variables.

### 💻 Setup your environment
- Create a virtual environment
```bash
python -m venv .venv
```
### ✅ Activate it
- If you are from linux activate it with
```bash
. .venv/bin/activate
```
- If you are from windows activate it with
```bash
. .venv/Scripts/activate
```

### 📥 Install requirements
```bash
pip install -r requirements.txt
```


> [!TIP]
> If you find **NinjaAioCruf** useful, consider :star: this project
> and why not ... [Buy me a coffee](https://buymeacoffee.com/caspel26)


### 🚀 Usage
## ModelSerializer
- You can serialize your models using ModelSerializer and made them inherit from it. In your models.py import ModelSerializer
```Python
from ninja-aio.models import ModelSerializer


class Foo(ModelSerializer):
  name = mdoels.CharField()
  bar = models.CharField()

  class ReadSerializer:
    fields = ["id", "name", "bar"]

  class CreateSerializer:
    fields = ["name", "bar"]

  class UpdateSerializer:
    fields = ["name", "bar"]
```
- ReadSerializer, CreateSerializer, UpdateSerializer are used to define which fields would be included in runtime schemas creation.

## APIViewSet
- View class used to automatically generate CRUD views. in your views.py import APIViewSet and define your api using NinjaAPI class. As Parser and Render of the API you must ninja-aio built-in classes which will serialize data using orjson.
```Python
from ninja import NinjAPI
from ninja-aio.views import APIViewSet
from ninja-aio.parsers import ORJSONParser
from ninja-aio.renders import ORJSONRender

from .models import Foo

api = NinjaAPI(renderer=ORJSONRenderer(), parser=ORJSONParser())


class FooAPI(APIViewSet):
  model = Foo
  api = api

  
FooAPI().add_views_route()
```
- and that's it, your model CRUD will be automatically created. You can also add custom views to CRUD overriding the built-in method "views".
```Python
from ninja import NinjAPI, Schema
from ninja-aio.views import APIViewSet
from ninja-aio.parsers import ORJSONParser
from ninja-aio.renders import ORJSONRender

from .models import Foo

api = NinjaAPI(renderer=ORJSONRenderer(), parser=ORJSONParser())


class ExampleSchemaOut(Schema):
  sum: float


class ExampleSchemaIn(Schema):
  n1: float
  n2: float


class FooAPI(APIViewSet):
  model = Foo
  api = api

  def views(self):
    @self.router.post("numbers-sum/", response={200: ExampleSchemaOut)
    async def sum(request: HttpRequest, data: ExampleSchemaIn):
        return 200, {sum: data.n1 + data.n2}


FooAPI().add_views_route()
```

## APIView
- View class to code generic views class based. In your views.py import APIView class.
```Python
from ninja import NinjAPI, Schema
from ninja-aio.views import APIView
from ninja-aio.parsers import ORJSONParser
from ninja-aio.renders import ORJSONRender

api = NinjaAPI(renderer=ORJSONRenderer(), parser=ORJSONParser())


class ExampleSchemaOut(Schema):
  sum: float


class ExampleSchemaIn(Schema):
  n1: float
  n2: float


class SumView(APIView):
  api = api
  api_router_path = "numbers-sum/"
  router_tag = "Sum"

  def views(self):
    @self.router.post("numbers-sum/", response={200: ExampleSchemaOut)
    async def sum(request: HttpRequest, data: ExampleSchemaIn):
        return 200, {sum: data.n1 + data.n2}


SumView().add_views_route()
```

### 🔒 Authentication
## Jwt
- AsyncJWTBearer built-in class is an authenticator class which use joserfc module. It cames out with authenticate method which validate given claims. Extend it to write your own authentication method. Default algorithms used is RS256.
```Python
from ninja-aio.auth import AsyncJWTBearer
from django.conf import settings

from .models import Foo


class CustomJWTBearer(AsyncJWTBearer):
    jwt_public = settings.JWT_PUBLIC
    claims = {"foo_id": {"required": True}}

    async def authenticate(self, request, token):
      super().authenticate(request, token)
      try:
        request.user = await Foo.objects.aget(id=self.dcd.claims["foo_id"])
      except Foo.DoesNotExist:
        return None
      return request.user
```
- Then add it to views.
```Python
from ninja import NinjAPI
from ninja-aio.views import APIViewSet, APIView
from ninja-aio.parsers import ORJSONParser
from ninja-aio.renders import ORJSONRender

from .models import Foo

api = NinjaAPI(renderer=ORJSONRenderer(), parser=ORJSONParser())


class FooAPI(APIViewSet):
  model = Foo
  api = api
  auths = CustomJWTBearer()


class ExampleSchemaOut(Schema):
  sum: float


class ExampleSchemaIn(Schema):
  n1: float
  n2: float


class SumView(APIView):
  api = api
  api_router_path = "numbers-sum/"
  router_tag = "Sum"
  auths = CustomJWTBearer()

  def views(self):
    @self.router.post("numbers-sum/", response={200: ExampleSchemaOut, auth=self.auths)
    async def sum(request: HttpRequest, data: ExampleSchemaIn):
        return 200, {sum: data.n1 + data.n2}


FooAPI().add_views_route()
SumView().add_views_route()
```

## 📌 Notes
- Feel free to contribute and improve the program. 🛠️
