import json
import re
from abc import ABC, abstractmethod
from collections import UserList
from copy import deepcopy
from functools import cached_property
from typing import Annotated, Any, Generic, Self, TypeVar, get_args, get_origin

from pydantic import (
    BaseModel,
    GetCoreSchemaHandler,
    ModelWrapValidatorHandler,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import core_schema

from cdktf_helpers.settings import computed_field
from cdktf_helpers.utils import extract_default

from .utils import boto3_session

VpcId = Annotated[str, StringConstraints(pattern=r"^vpc-[a-z0-9]+$")]
SubnetId = Annotated[str, StringConstraints(pattern=r"^subnet-[a-z0-9]+$")]
HostedZoneId = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9]+$")]


class NestedResourceMixin:
    @model_validator(mode="wrap")
    @classmethod
    def nested_resource(
        cls, data: Any, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        return_data = deepcopy(data)
        if isinstance(data, dict):
            for field_name, field in cls.model_fields.items():
                origin = get_origin(field.annotation) or field.annotation
                is_class = isinstance(origin, type)
                is_resource = is_class and issubclass(origin, AwsResource)
                is_resource_list = is_class and issubclass(origin, AwsResources)
                value = data.get(field_name, None)
                if not value:
                    value = extract_default(field)
                if value is not None:
                    if is_resource and isinstance(value, str):
                        value = origin(id=value)
                    elif is_resource_list and isinstance(value, list):
                        type_args = get_args(field.annotation)
                        resource_cls = next(
                            arg for arg in type_args if issubclass(arg, AwsResource)
                        )
                        if resource_cls:
                            value = AwsResources([resource_cls(id=id) for id in value])
                    else:
                        pass
                return_data[field_name] = value
        return handler(return_data)


class AwsResource(NestedResourceMixin, BaseModel, ABC):
    id: str

    @property
    @abstractmethod
    def resource(self):
        pass

    def __str__(self):
        return self.id

    def __repr__(self):
        return f"{type(self).__name__}('{self.id})'"

    def __eq__(self, other):
        return other and isinstance(other, type(self)) and str(other) == str(self)


AwsResourceType = TypeVar("AwsResourceType", bound=AwsResource)


class AwsResources(UserList[AwsResourceType], Generic[AwsResourceType]):
    @property
    def ids(self):
        return [str(r) for r in self]

    @classmethod
    def _validate(cls, value: Any, _) -> "AwsResources[AwsResourceType]":
        if isinstance(value, cls):
            return value
        if isinstance(value, list):
            return cls(value)
        raise ValueError(f"Expected list or {cls.__name__}, got {type(value)}")

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        list_schema = handler.generate_schema(list[Any])
        return core_schema.no_info_wrap_validator_function(cls._validate, list_schema)

    def __str__(self):
        return json.dumps(self.ids)

    def __repr__(self):
        return f"{type(self).__name__}({repr(self.ids)})"

    def __contains__(self, resource_or_id: Any):
        if isinstance(resource_or_id, AwsResource):
            return super().__contains__(resource_or_id)
        return resource_or_id in (str(r) for r in self)


class Vpc(AwsResource):
    id: VpcId

    @cached_property
    def resource(self):
        resource = boto3_session().resource("ec2").Vpc(self.id)
        resource.load()
        return resource


class Subnet(AwsResource):
    id: SubnetId

    @cached_property
    def resource(self):
        resource = boto3_session().resource("ec2").Subnet(self.id)
        resource.load()
        return resource

    @computed_field("Subnet CIDR block")
    def cidr_block(self) -> str:
        return self.resource.cidr_block


class HostedZone(AwsResource):
    id: HostedZoneId

    @field_validator("id", mode="before")
    @classmethod
    def strip_id_prefix(cls, value: str) -> str:
        return re.sub(r"^/hostedzone/", "", value)

    @cached_property
    def resource(self):
        route53 = boto3_session().client("route53")
        response = route53.get_hosted_zone(Id=self.id)
        return response["HostedZone"]

    @computed_field
    def long_id(self) -> str:
        return f"/hostedzone/{self.id}"

    @computed_field
    def name(self) -> str:
        return self.resource["Name"]
