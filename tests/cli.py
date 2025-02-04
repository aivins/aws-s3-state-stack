from typing import List

from pydantic import Field

from cdktf_helpers.settings import computed_field
from cdktf_helpers.settings.aws import AwsAppSettings, Vpc, VpcField
from cdktf_helpers.stacks import AwsS3StateStack


class Settings(AwsAppSettings):
    vpc: Vpc = VpcField()
    colour: str = Field(default="green", description="Some random colour")
    animals: List[str] = Field(
        default=["Dog", "Cat", "Stegosaurus"], description="Some animals"
    )
    comment: str = Field(default="", description="Just an extra comment")

    @computed_field
    def comment_upper(self):
        return self.comment.upper()


class Stack(AwsS3StateStack[Settings]):
    def build(self):
        pass
