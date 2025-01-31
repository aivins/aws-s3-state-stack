import boto3
from cdktf import App

from cdktf_helpers.settings import AppSettings, AwsAppSettings


class AwsApp(App):
    def __init__(self, settings, **kwargs):
        super().__init__(**kwargs)
        self.serialize_settings(settings)

    def serialize_settings(self, settings):
        self.node.set_context("settings", settings.model_dump())
