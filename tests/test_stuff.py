from typing import Any, List

from pydantic import BaseModel, RootModel


class Thing(BaseModel):
    name: str = "something"


class Stuff(RootModel[List[Any]]):
    def __iter__(self):
        return iter(self.__root__)

    def append(self, item):
        self.__root__.append(item)


def test_stuff():
    things = [Thing() for _ in range(3)]
    stuff = Stuff(things)
