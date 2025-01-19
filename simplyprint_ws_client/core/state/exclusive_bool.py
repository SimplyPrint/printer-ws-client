__all__ = ['ExclusiveBool']

from pydantic import BaseModel, model_serializer


class ExclusiveBool(BaseModel):
    """Special wrapper boolean class that will make all true
    values unique. So all assignments = True will be marked
    as a change."""
    value: bool = False

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        # True != True
        if other.value is True:
            return False

        return self.value == other.value

    def __bool__(self):
        return self.value

    def __repr__(self):
        return repr(self.value)

    @model_serializer()
    def serialize(self):
        return self.value
