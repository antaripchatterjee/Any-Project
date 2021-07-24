import abc
from .prompt import Prompts

class ValidationError(Exception):
    pass


class ValidationResult:
    def __init__(self, successful, msg):
        self.__successful = successful
        self.__msg = msg

    @property
    def successful(self): return self.__successful

    @property
    def message(self): return self.__msg


class Setup(abc.ABC):
    def __init__(self, action_name):
        self.prompts = Prompts()
        self.current_action = action_name

    @abc.abstractmethod
    def pre_validation(self):
        pass

    @abc.abstractmethod
    def set_prompts(self):
        pass

    @abc.abstractmethod
    def on_task(self, task):
        pass

    @abc.abstractmethod
    def post_validation(self):
        pass

    def on_create_file(self, filename):
        return True

    def on_create_folder(self, directory):
        return True


class DefaultSetup(Setup):        
    def pre_validation(self):
        return ValidationResult(True, None)

    def set_prompts(self):
        pass

    def on_task(self, task):
        pass

    def post_validation(self):
        return ValidationResult(True, None)


