from pydantic import BaseModel

from cdktf_helpers.settings import computed_field


def test_custom_computed_field():
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

    model = Model(name="Andy", age=46)
    # With a @property
    assert model.name_and_age == "Andy is 46 years old"

    # Without a @propety
    assert model.is_old == "Andy is old!"
