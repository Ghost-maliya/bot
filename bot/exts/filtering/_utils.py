import importlib
import importlib.util
import inspect
import pkgutil
from abc import ABC
from collections import defaultdict
from typing import Set


def subclasses_in_package(package: str, prefix: str, parent: type) -> Set[type]:
    """Return all of the subclasses of class `parent`, found in the top-level of `package`, given by absolute path."""
    subclasses = set()

    # Find all modules in the package.
    for module_info in pkgutil.iter_modules([package], prefix):
        if not module_info.ispkg:
            module = importlib.import_module(module_info.name)
            # Find all classes in each module...
            for _, class_ in inspect.getmembers(module, inspect.isclass):
                # That are a subclass of the given class.
                if parent in class_.__bases__:
                    subclasses.add(class_)

    return subclasses


class FieldRequiring(ABC):
    """An abstract class that can force its concrete subclasses to set a value for specific class attributes."""

    # Sentinel value that mustn't remain in a concrete subclass.
    MUST_SET = object()

    # Sentinel value that mustn't remain in a concrete subclass.
    # Overriding value must be unique in the subclasses of the abstract class in which the attribute was set.
    MUST_SET_UNIQUE = object()

    # A mapping of the attributes which must be unique, and their unique values, per FieldRequiring subclass.
    _unique_attributes: defaultdict[type, dict[str, set]] = defaultdict(dict)

    def __init_subclass__(cls, **kwargs):
        # If a new attribute with the value MUST_SET_UNIQUE was defined in an abstract class, record it.
        if inspect.isabstract(cls):
            for attribute in dir(cls):
                if getattr(cls, attribute, None) == FieldRequiring.MUST_SET_UNIQUE:
                    for parent in cls.__mro__[1:-1]:  # The first element is the class itself, last element is object.
                        if hasattr(parent, attribute):  # The attribute was inherited.
                            break
                    else:
                        # A new attribute with the value MUST_SET_UNIQUE.
                        FieldRequiring._unique_attributes[cls][attribute] = set()
            return

        for attribute in dir(cls):
            if attribute.startswith("__") or attribute in ("MUST_SET", "MUST_SET_UNIQUE"):
                continue
            value = getattr(cls, attribute)
            if value is FieldRequiring.MUST_SET:
                raise ValueError(f"You must set attribute {attribute!r} when creating {cls!r}")
            elif value is FieldRequiring.MUST_SET_UNIQUE:
                raise ValueError(f"You must set a unique value to attribute {attribute!r} when creating {cls!r}")
            else:
                # Check if the value needs to be unique.
                for parent in cls.__mro__[1:-1]:
                    # Find the parent class the attribute was first defined in.
                    if attribute in FieldRequiring._unique_attributes[parent]:
                        if value in FieldRequiring._unique_attributes[parent][attribute]:
                            raise ValueError(f"Value of {attribute!r} in {cls!r} is not unique for parent {parent!r}.")
                        else:
                            # Add to the set of unique values for that field.
                            FieldRequiring._unique_attributes[parent][attribute].add(value)
