from typing import Annotated

from pydantic import StringConstraints

Vpc = Annotated[str, StringConstraints(pattern=r"^vpc-[a-z0=9]+$")]
Subnet = Annotated[str, StringConstraints(pattern=r"^subnet-[a-z0=9]+$")]
