from any_project import __program__
from any_project import __version__
from any_project import __desc__
from any_project.application import Actions
from dotenv import load_dotenv
import os, re
from argparse import ArgumentParser
from pymsgprompt.logger import pinfo, perror

def main():
    dotenv_path = os.path.relpath(
        os.path.join(os.getcwd(), '.env')
    )
    if os.path.isfile(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
    parser = ArgumentParser(prog=__program__, description=__desc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-init', '-i', action='store', type=str, default=None, \
        help='Initialize a project')
    group.add_argument('-build', '-b', action='store', type=str, default=None, \
        help='Build a project from a initialized yaml code')
    parser.add_argument('-task', '-t', dest='tasks', action='append', \
        default=[], help='''Specify tasks to run while building,
        only usable with `build` option.
    ''')
    parser.add_argument('-v', action='version', version='%(prog)s - ' + __version__)
    parser.add_argument('-version', action='version', version=__version__)
    results = parser.parse_args()

    if results.init is not None:
        if len(results.tasks) > 0:
            parser.error('argument `-task` can only be used with `-build`')
        pattern = r'^([^\:]+)(?:\:([a-z0-9_][a-z0-9_\-]*))?$'
        m = re.match(pattern, results.init.strip(), flags=re.IGNORECASE)
        if m is None:
            parser.error('argument value of `-init` is invalid')
        else:
            target_dir, project_name = m.groups()
        target_dir = os.path.abspath(target_dir)
        project_name = re.sub(r'[^a-z0-9_\-]', '_', \
            os.path.basename(target_dir), flags=re.IGNORECASE) \
                if project_name is None else project_name
        project_structure_yaml = Actions.init(target_dir, project_name)
        if project_structure_yaml is None :
            perror('Could not initialize project structure.')
            exit(-1)
        else:
            pinfo(f'Project structure created at "{project_structure_yaml}"')
    else:
        tasks = [] if results.tasks is None else results.tasks
        pattern = r'^[\s]*([^\:\?]+)(?:\:([a-z_][a-z0-9_]*))?[\s]*$' # + \
            # '(?:\?((?:[a-z_][a-z_0-9]*)(?:\;[a-z_][a-z0-9_]*)*))?$'
        m = re.match(pattern, results.build, flags=re.IGNORECASE)
        if m is None:
            parser.error('argument value of `-build` is invalid')
        else:
            # target_dir, action_name, tasks = m.groups()
            project_dir, action_name = m.groups()
            if action_name is None:
                action_name = 'default'
        project_dir = os.path.abspath(project_dir)
        structure_yaml = os.path.join(project_dir, 'project-structure.yaml')
        print(structure_yaml, action_name, tasks)
        Actions.build(structure_yaml, action_name, tasks)
