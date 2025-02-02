
from cdktf import App


class AwsApp(App):
    def __init__(self, settings, **kwargs):
        super().__init__(**kwargs)
        self.settings = settings
