from typing import List

from pydantic import Field

from cdktf_helpers.settings import computed_field
from cdktf_helpers.settings.aws import (
    AwsAppSettings,
    AwsResources,
    Subnet,
    SubnetsField,
    Vpc,
    VpcField,
)
from cdktf_helpers.stacks import AwsS3StateStack


class Settings(AwsAppSettings):
    vpc: Vpc = VpcField()
    subnets: AwsResources[Subnet] = SubnetsField()
    colour: str = Field(default="green", description="Some random colour")
    animals: list[str] = Field(
        default=["Dog", "Cat", "Stegosaurus"], description="Some animals"
    )
    comment: str = Field(default="", description="Just an extra comment")

    @computed_field("Upper case of comment")
    def comment_upper(self) -> str:
        return self.comment.upper()


class Stack(AwsS3StateStack[Settings]):
    def build(self):
        pass
