import json
from abc import ABC, abstractmethod
from collections import UserList
from functools import cached_property
from reprlib import repr
from typing import Annotated, Any, Generic, Iterator, List, TypeVar

from pydantic import BaseModel, Field, StringConstraints
from pydantic_core import core_schema

from cdktf_helpers.settings import computed_field

from .utils import boto3_session

VpcId = Annotated[str, StringConstraints(pattern=r"^vpc-[a-z0-9]+$")]
SubnetId = Annotated[str, StringConstraints(pattern=r"^subnet-[a-z0-9]+$")]
HostedZoneId = Annotated[str, StringConstraints(pattern=r"^/hostedzone/[A-Z0-9]+$")]


class AwsResource(BaseModel, ABC):
    @property
    @abstractmethod
    def resource(self):
        pass

    def __str__(self):
        return self.id

    def __eq__(self, other):
        return other and isinstance(other, type(self)) and str(other) == str(self)


AwsResourceType = TypeVar("AwsResourceType", bound=AwsResource)


class AwsResources(BaseModel, Generic[AwsResourceType]):
    _items: List[AwsResourceType] = Field(default_factory=list, exclude=True)

    def __init__(self, initlist: List[AwsResourceType] = []):
        self._validate(*initlist)
        super().__init__()
        self._items = initlist

    @property
    def ids(self):
        return [str(r) for r in self._items]

    def __getitem__(self, index: int) -> AwsResourceType:
        return self._items[index]

    def __setitem__(self, index: int, value: AwsResourceType):
        self._items[index] = value

    def __delitem__(self, index: int):
        del self._items[index]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[AwsResourceType]:
        return iter(self._items)

    def append(self, item: AwsResourceType):
        self._items.append(item)

    def extend(self, items: List[AwsResourceType]):
        self._items.extend(items)

    def pop(self, index: int = -1) -> AwsResourceType:
        return self._items.pop(index)

    def clear(self):
        self._items.clear()

    def insert(self, index: int, item: AwsResourceType):
        self._items.insert(index, item)

    def remove(self, item: AwsResourceType):
        self._items.remove(item)

    def index(self, item: AwsResourceType) -> int:
        return self._items.index(item)

    def count(self, item: AwsResourceType) -> int:
        return self._items.count(item)

    def sort(self, *, key=None, reverse=False):
        self._items.sort(key=key, reverse=reverse)

    def reverse(self):
        self._items.reverse()

    def __repr__(self):
        return f"{type(self).__name__}({self.ids})"

    def __contains__(self, resource_or_id: Any):
        if isinstance(resource_or_id, AwsResource):
            return resource_or_id in self._items
        return resource_or_id in self.ids


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

    @cached_property
    def resource(self):
        route53 = boto3_session().client("route53")
        response = route53.get_hosted_zone(Id=self.id)
        return response["HostedZone"]

    @computed_field
    def name(self) -> str:
        return self.resource["Name"]
