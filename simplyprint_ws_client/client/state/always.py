from traitlets import HasTraits, TraitType
from typing import Any


class Always(TraitType):
    """ 
    Wrap a trait type with custom setter logic.
    """

    def __init__(self, trait: TraitType):
        self._trait = trait

        # Loop over all functions in the trait
        for name in dir(trait):
            # If it's a function, and not a private function
            if name in ["set"] or name.startswith("__"):
                continue

            value = getattr(trait, name)

            is_callable = callable(value)

            if not is_callable and not hasattr(self, name):
                setattr(self, name, value)

            if not is_callable:
                continue

            # Make a wrapper so self is _trait
            def make_wrapper(trait, name):
                def wrapper(*args, **kwargs):
                    return getattr(trait, name)(*args, **kwargs)

                return wrapper

            # Set the wrapper to the trait
            setattr(self, name, make_wrapper(trait, name))

    @property
    def name(self):
        """ 
        A traitlets name is dynamically generated so we make it accessible
        as a property.
        """
        return self._trait.name

    def set(self, obj: HasTraits, value: Any):
        """ 
        Re-implementation of TraitType.set from 
        https://github.com/ipython/traitlets/blob/main/traitlets/traitlets.py#L689

        to always notify observers when a value has been set
        not just when it has new information.
        """
        new_value = self._validate(obj, value)
        assert self.name is not None
        try:
            old_value = obj._trait_values[self.name]
        except KeyError:
            old_value = self.default_value

        obj._trait_values[self.name] = new_value

        # Always notify
        obj._notify_trait(self.name, old_value, new_value)
