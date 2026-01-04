from ninja_aio.factory import ApiMethodFactory

api_get = ApiMethodFactory.make("get")
api_post = ApiMethodFactory.make("post")
api_put = ApiMethodFactory.make("put")
api_patch = ApiMethodFactory.make("patch")
api_delete = ApiMethodFactory.make("delete")
api_options = ApiMethodFactory.make("options")
api_head = ApiMethodFactory.make("head")
