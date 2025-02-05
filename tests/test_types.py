import boto3
from moto import mock_aws
from pydantic import BaseModel

from cdktf_helpers.settings import computed_field
from cdktf_helpers.settings.aws import (
    AwsResource,
    AwsResources,
    HostedZone,
    Subnet,
    Vpc,
)


def test_resource():
    class Resource(AwsResource):
        id: str

        def resource(self):
            return {"id": self.id}

    class Parent(AwsResource):
        id: str
        thing: Resource
        stuff: AwsResources[Resource]

        def resource(self):
            return {"id": self.id}

    parent = Parent(id="blah", thing="12345", stuff=["abc", "def"])
    assert isinstance(parent.thing, Resource)
    assert parent.thing.id == "12345"
    assert isinstance(parent.stuff, AwsResources)
    assert all(isinstance(r, Resource) for r in parent.stuff)


def test_computed_field():
    class Model(BaseModel):
        name: str
        age: int

        @computed_field("Name and Age")
        @property
        def name_and_age(self) -> str:
            return f"{self.name} is {self.age} years old"

        @computed_field("Is person old?")
        def is_old(self) -> str:
            if self.age > 40:
                return f"{self.name} is old!"
            return f"{self.name} is still wet behind the ears"

        @computed_field
        def is_legend(self) -> bool:
            return True

    andy = Model(name="Andy", age=46)
    # With a @property
    assert andy.name_and_age == "Andy is 46 years old"

    # Without a @propety
    assert andy.is_old == "Andy is old!"

    # No args decorator
    assert andy.is_legend is True


def test_collection():
    with mock_aws():
        subnet1 = Subnet(id="subnet-123")
        subnet2 = Subnet(id="subnet-456")
        subnet3 = Subnet(id="subnet-789")
        subnets: AwsResources[Subnet] = AwsResources([subnet1, subnet2, subnet3])
        assert subnets.ids == ["subnet-123", "subnet-456", "subnet-789"]
        assert (
            repr(subnets) == "AwsResources(['subnet-123', 'subnet-456', 'subnet-789'])"
        )


def test_collection_with_model():
    with mock_aws():

        class Model(BaseModel):
            subnets: AwsResources[Subnet]

        subnet1 = Subnet(id="subnet-123")
        subnet2 = Subnet(id="subnet-456")
        subnet3 = Subnet(id="subnet-789")

        # Passed in as a plain list
        instance = Model(subnets=[subnet1, subnet2, subnet3])
        assert isinstance(instance.subnets, AwsResources)

        # Passed in as AwsResources
        instance = Model(subnets=AwsResources([subnet1, subnet2, subnet3]))
        assert isinstance(instance.subnets, AwsResources)


def test_type_equality():
    with mock_aws():
        assert Vpc(id="vpc-12345") == Vpc(id="vpc-12345")
        assert Vpc(id="vpc-12345") != Vpc(id="vpc-67890")


def test_contains():
    with mock_aws():
        subnet1 = Subnet(id="subnet-123")
        subnet2 = Subnet(id="subnet-456")
        subnet3 = Subnet(id="subnet-789")
        subnets: AwsResources[Subnet] = AwsResources([subnet1, subnet2])
        assert subnet1 in subnets
        assert subnet2 in subnets
        assert subnet3 not in subnets
        assert subnet1.id in subnets
        assert subnet2.id in subnets
        assert subnet3.id not in subnets


def test_vpc():
    with mock_aws():
        vpc_id = list(boto3.Session().resource("ec2").vpcs.all())[0].id
        vpc = Vpc(id=vpc_id)
        assert vpc.resource.cidr_block


def test_subnet():
    with mock_aws():
        subnet = list(boto3.Session().resource("ec2").subnets.all())[0]
        subnet_id = subnet.id
        cidr_block = subnet.cidr_block
        subnet = Subnet(id=subnet_id)
        assert subnet.id == subnet_id
        assert subnet.cidr_block == cidr_block


def test_hosted_zone():
    with mock_aws():
        route53 = boto3.Session().client("route53")
        response = route53.create_hosted_zone(Name="blah.com", CallerReference="dummy")
        zone = HostedZone(id=response["HostedZone"]["Id"])
        assert zone.name == "blah.com."
