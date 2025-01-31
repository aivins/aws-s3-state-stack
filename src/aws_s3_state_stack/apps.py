import boto3
from cdktf import App

from aws_s3_state_stack.settings import AppSettings, AwsAppSettings


class AwsApp(App):
    def __init__(self, settings, **kwargs):
        self.settings = self.init_settings(settings)
        super().__init__(**kwargs)

    def init_settings(self, settings):
        for key, setting in settings.model_dump().items():
            breakpoint()
