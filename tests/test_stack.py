import pytest
from cdktf import Testing
from cdktf_cdktf_provider_aws.instance import Instance

from .main import MyStack


def test_should_contain_correct_instance(synthesized):
    with synthesized(MyStack) as synthesized:
        assert Testing.to_have_resource_with_properties(
            synthesized,
            Instance.TF_RESOURCE_TYPE,
            {"ami": "ami-0d11f9bfe33cfbe8b", "instance_type": "t2.micro"},
        )


def test_check_validity(fully_synthesized):
    with fully_synthesized(MyStack) as fully_synthesized:
        assert Testing.to_be_valid_terraform(fully_synthesized)
