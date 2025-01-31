import types

from cdktf import App


class AwsApp(App):
    def __init__(self, settings, **kwargs):
        super().__init__(**kwargs)

        self.node.set_context("settings", settings.model_dump())

        def deserialize(self):
            settings_dict = self.node.get_context("settings")
            settings_dict.update(
                {"app": settings.app, "environment": settings.environment}
            )
            return type(settings).model_validate(settings_dict)

        self.get_settings = types.MethodType(deserialize, self)
