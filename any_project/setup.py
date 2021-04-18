import abc
from .prompt import Prompts

class Setup(abc.ABC):
    def __init__(self, constants):
        self.prompts = Prompts()
        def try_getattr(key, constants=constants):
            try:
                return getattr(constants, key)
            except AttributeError:
                return None
        self.get_constant = lambda key: try_getattr(key)
    
    @abc.abstractmethod
    def do_pre_validations(self):
        pass

    @abc.abstractmethod
    def set_prompts(self):
        pass

    @abc.abstractmethod
    def do_task_on(self, task):
        pass

    @abc.abstractmethod
    def do_post_validations(self):
        pass

    def on_create_file(self, filename):
        return True

    def on_create_folder(self, directory):
        return True


class DefaultSetup(Setup):        
    def do_pre_validations(self):
        pass

    def set_prompts(self):
        pass

    def do_task_on(self, task):
        pass

    def do_post_validations(self):
        pass


