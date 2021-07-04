from pymsgprompt.logger import pwarn


class Constant(object):
    def __init__(self, _value):
        self.__value__ = _value

    def __set__(self, instance, value):
        pwarn(f'Can not reassign a constant to "{value}"')
    
    def __get__(self, instance, owner):
        return self.__value__
        