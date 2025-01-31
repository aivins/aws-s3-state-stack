# aws-s3-state-stack

Experimental CDKTF Stack that automatically registers an AWS Provider and and S3Backend with DynamoDB locking. It can even create these automatically, which might be a really bad idea in real life but was an interesting experiment all the same.

## Example Usage

Requires an working AWS CLI session in the environment it is run. `cdktf deploy` will create the state backend resources via AWS API calls, then deploy the resources using that backend for state management.


```python
#!/usr/bin/env python

from cdktf import App, TerraformOutput
from cdktf_cdktf_provider_aws.instance import Instance

from cdktf_helpers import AwsS3StateStack


class MyStack(AwsS3StateStack):
    def build(self):
        instance = Instance(
            self,
            "compute",
            ami="ami-0d11f9bfe33cfbe8b",
            instance_type="t2.micro",
        )

        TerraformOutput(
            self,
            "public_ip",
            value=instance.public_ip,
        )


if __name__ == "__main__":
    app = App(context={"name": "aivinstest"})
    stack = MyStack(app, "test_stack")
    app.synth()
```

## Testing

Incudes a pytest plugin that registers some factory fixtures that mock out the backend. They otherwise use the usual cdk.Testing functions. They all take you stack class under test (which must be a subclass of AwsS3StateStack) as an argument.

- `stack` returns a mocked out version of the stack wrapped in `Testing.app()`.
- `synthesized` returns the JSON output of `Testing.synth()`
- `fully_synthesized` returns a path to a directory created by `Testing.full_synth()`

```python
import pytest
from cdktf import Testing
from cdktf_cdktf_provider_aws.instance import Instance

from main import MyStack


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
```