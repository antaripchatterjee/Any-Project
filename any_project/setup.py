import abc
from .prompt import Prompts


class Setup(abc.ABC):
    def __init__(self, action_name):
        self.prompts = Prompts()
        self.current_action = action_name

    @abc.abstractmethod
    def pre_validations(self):
        pass

    @abc.abstractmethod
    def set_prompts(self):
        pass

    @abc.abstractmethod
    def on_task(self, task):
        pass

    @abc.abstractmethod
    def post_validations(self):
        pass

    def on_create_file(self, filename):
        return True

    def on_create_folder(self, directory):
        return True


class DefaultSetup(Setup):        
    def pre_validations(self):
        pass

    def set_prompts(self):
        pass

    def on_task(self, task):
        pass

    def post_validations(self):
        pass


