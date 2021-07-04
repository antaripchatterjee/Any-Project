from any_project.setup import DefaultSetup
from any_project.setup import Setup

__program__ = __name__.split('/.')[-1].replace('_', '-').title()
__version__ = '0.0.7'
__module__ = __name__
__desc__ = '''
    {0} is a python module, helps to build a basic skeleton file structure of any project.
'''.format(__program__)
