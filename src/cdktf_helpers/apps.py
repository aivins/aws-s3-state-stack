import boto3
from cdktf import App

from cdktf_helpers.settings import AppSettings, AwsAppSettings


class AwsApp(App):
    def __init__(self, settings, **kwargs):
        super().__init__(**kwargs)
        self.settings = self.init_settings(settings)

    def init_settings(self, settings):
        # Add some of the private fields to context explicitly
        self.node.set_context("app", settings.app)
        self.node.set_context("environment", settings.environment)
        self.node.set_context("namespace", settings.namespace)

        # Add all the normal fields to context
        for key, setting in settings.model_dump().items():
            self.node.set_context(key, setting)
