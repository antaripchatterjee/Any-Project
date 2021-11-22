from any_project.setup import DefaultSetup
from any_project.setup import Setup

__program__ = __name__.split('/.')[-1].replace('_', '-').title()
__version__ = '0.2.0b1'
__module__ = __name__
__desc__ = f'''
    {__program__} is a python module, helps to build any
    basic skeleton file structure of "any project".
'''.replace('\n    ', ' ').strip()
