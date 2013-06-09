# coding: utf-8
"""
This module contains fields classes. Each of them knows about structures which
they can manipulate and how to fetch key and value for using in dehydrating
process.
This classes separated from Dehydrator class for ease of extending and adding
new field types.
"""
from __future__ import unicode_literals

from collections import Iterable, Mapping
from functools import partial
from operator import attrgetter

from .helpers import Registry
from .exceptions import SpecParsingError

registry = Registry()

# some handy shortcuts
is_string = lambda val: isinstance(val, basestring)
is_dict = lambda val: isinstance(val, Mapping)
is_iterable = lambda val: isinstance(val, Iterable)
is_pair = lambda val: is_iterable(val) and len(val) == 2


class Field(object):

    def __init__(self, dehydrator, spec):
        self.dehydrator = dehydrator
        self.target_info, self.substitution = self.parse_spec(spec)

    @staticmethod
    def is_relevant(spec):
        """
        Field classes knows about specification of structures, which are
        relevant for them. So it can inform us whether this particular
        specification is acceptable by redefining this method.
        """
        raise NotImplementedError

    def parse_spec(self, spec):
        """
        You should raise SpecParsingError if something goes wrong.
        TODO: Maybe *I* should catch all exceptions and raise SpecParsingError?
        """
        if is_pair(spec):
            target_info, substitution = spec
        else:
            target_info = spec
            substitution = None

        try:
            self.validate_target_info(target_info)
        except Exception as e:
            raise SpecParsingError(e.message)

        return target_info, substitution

    def validate_target_info(self, target_info):
        """
        Hook for validate target info, i. e. check keys or attributes if it is
        complex structure.
        """
        pass

    def build_key(self):
        return self.substitution or self.target

    def resolve_target(self, obj, target_name):
        # try to find getter method on dehydrator at first
        dehydrator_getter_name = self.dehydrator.GETTER_PREFIX + target_name
        if hasattr(self.dehydrator, dehydrator_getter_name):
            return getattr(self.dehydrator, dehydrator_getter_name)

        if hasattr(obj, target_name):
            object_attribute = getattr(obj, target_name)
            if callable(object_attribute):
                return object_attribute
            else:
                return partial(attrgetter(object_attribute), obj)


@registry.register
class SimpleField(Field):

    @staticmethod
    def is_relevant(spec):
        if is_string(spec):
            return True
        if is_pair(spec) and all(map(is_string, spec)):
            return True
        return False

    @property
    def target(self):
        return self.target_info

    def build_value(self, obj):
        target_getter = self.resolve_target(obj=obj, target_name=self.target)
        return target_getter(obj)



@registry.register
class ComplexField(Field):

    TARGET_FIELD_NAME = 'target'
    ITERABLE_FLAG_FIELD_NAME = 'iterable'
    DEHYDRATOR_FIELD_NAME = 'dehydrator'

    @staticmethod
    def is_relevant(spec):
        if is_dict(spec):
            return True
        if (is_pair(spec) and
            is_dict(spec[0]) and
            is_string(spec[1])):
            return True
        return False

    def validate_target_info(self, target_info):
        if not self.TARGET_FIELD_NAME in target_info:
            message = (
                "'{field_name}' field is required in specification "
                "of {class_name}"
            )
            raise SpecParsingError(message=message.format(
                field_name=self.TARGET_FIELD_NAME,
                class_name=self.__class__.__name__,
            ))

    def build_value(self, obj):
        target_getter = self.resolve_target(obj=obj, target_name=self.target)
        target = target_getter(obj)

        dehydrator = self.dehydrator_cls(fields=self.fields)
        if self.is_iterable:
            return map(dehydrator.dehydrate, target)
        else:
            return dehydrator.dehydrate(obj)


    @property
    def target(self):
        return self.target_info[self.TARGET_FIELD_NAME]

    @property
    def is_iterable(self):
        return self.target_info.get(self.ITERABLE_FLAG_FIELD_NAME, False)

    @property
    def dehydrator_cls(self):
        from dehydrate.base import Dehydrator
        return self.target_info.get(self.DEHYDRATOR_FIELD_NAME, Dehydrator)

    @property
    def fields(self):
        return self.target_info.get('fields')