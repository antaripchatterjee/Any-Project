from any_project import __program__
from any_project import __version__
from any_project import __module__
from any_project import Setup
from any_project.template import yaml_template
from any_project.constant import Constant
from collections import OrderedDict
from argparse import ArgumentParser
from yaml.loader import FullLoader
import oyaml as yaml
from pymsgprompt.logger import pinfo, perror, pwarn
from pymsgprompt.prompt import ask
import os
import re
import ast
import shutil
import git


class Actions(object):
    @staticmethod
    def init(target_dir, project_name):
        YAML_CODE_DICT = yaml_template(project_name, os.path.relpath(target_dir))
        try:
            os.makedirs(target_dir, exist_ok=True)
        except FileNotFoundError as e:
            perror(f"{type(e).__name__} -> {e}")
            return None
        project_structure_yaml = os.path.join(target_dir, 'project-structure.yaml')
        overwrite_option = None
        if os.path.isfile(project_structure_yaml):
            overwrite_option = ask('Do you want to overwrite the existing project structure?', choices=['yes', 'no'], default='no',
                on_error=lambda *argv: True)
        else:
            overwrite_option = 'yes'
        if overwrite_option == 'yes':
            with open(project_structure_yaml, 'w') as f:
                # f.write(YAML_CODE_STR)
                yaml.dump(YAML_CODE_DICT, f, indent=4)
        else:
            pwarn('Action has been prevented by user!')
            return None
        return project_structure_yaml

    @staticmethod
    def init_and_commit_git_repo(root, msg):
        try:
            try:
                repo = git.Repo(root)
            except git.exc.InvalidGitRepositoryError:
                pinfo('Initializing as a git repo')
                repo = git.Repo.init(root)
            pinfo('Adding all the files')
            repo.git.add(A=True)
            pinfo(f'Commit begin\nMessage:')
            print(msg)
            repo.git.commit(m=msg)
            return True, None
        except Exception as e:
            return False, e



    @staticmethod
    def expand_file_structure(root, structure, setup_obj, constants):
        for key, val in structure.items():
            key = key.strip()
            source = ''
            m = re.match(r'^\$(env|prompt|const)\:([^\s].*)$', key, flags=re.IGNORECASE)
            if m is not None:
                source, key = m.groups()
            if source.upper() == 'ENV':
                temp = key
                key = os.environ.get(temp)
                if not isinstance(key, str):
                    key = ''
                if key.strip() == '':
                    pwarn(f'Could not find enviornment value of key "{temp}"')
                    return False
            elif source.upper() == 'CONST':
                temp = key
                # key = Actions.__constants__.get(temp)
                try:
                    key = getattr(constants, temp)
                except AttributeError:
                    key = ''
                if not isinstance(key, str):
                    key = ''
                if key.strip() == '':
                    pwarn(f'Could not find constant value of key "{temp}"')
                    return False
            elif source.upper() == 'PROMPT':
                if setup_obj is None:
                    perror('No setup class has been created!')
                    return False
                temp = key
                key = setup_obj.prompts.__dict__.get(temp)
                if not isinstance(key, str):
                    key = ''
                if key.strip() == '':
                    perror(f'Could not find a valid value of the prompt "{temp}"')
                    return False

            if isinstance(val, str):
                new_file = os.path.relpath(os.path.join(root, key))
                if setup_obj is None:
                    write_file = True
                else:
                    write_file = setup_obj.on_create_file(new_file)
                if write_file:
                    pinfo(f'Creating file  : {new_file}')
                    try:
                        with open(new_file, 'a') as f:
                            f.write(os.path.expandvars(val).format(
                                prompts = setup_obj.prompts if setup_obj is not None else None,
                                consts = constants
                            ))
                    except (OSError, FileNotFoundError, NotADirectoryError) as e:
                        perror(f'Could not create file - {type(e).__name__}:{e}')
                        return False
                    except (KeyError, AttributeError) as e:
                        pwarn(f'{type(e).__name__} occurred while writing the file')
                        perror(f"Message: {e}")
                        return False
            else:
                if val is None:
                    new_folder = os.path.relpath(os.path.join(root, key))
                    if setup_obj is None:
                        write_directory = True
                    else:
                        write_directory = setup_obj.on_create_folder(new_folder)
                    if write_directory:
                        pinfo(f'Creating folder: {new_folder}')
                        try:
                            os.makedirs(new_folder, exist_ok=True)
                        except (OSError, FileNotFoundError, NotADirectoryError) as e:
                            perror(f'Could not create folder - {type(e).__name__}:{e}')
                            return False
                elif isinstance(val, (dict, OrderedDict)):
                    new_folder = os.path.relpath(os.path.join(root, key))
                    if setup_obj is None:
                        write_directory = True
                    else:
                        write_directory = setup_obj.on_create_folder(new_folder)
                    if write_directory:
                        pinfo(f'Creating folder: {new_folder}')
                        try:
                            os.makedirs(new_folder, exist_ok=True)
                            if not Actions.expand_file_structure(new_folder, val, setup_obj, constants):
                                return False
                        except (OSError, FileNotFoundError, NotADirectoryError) as e:
                            perror(f'Could not create folder - {type(e).__name__}:{e}')
                            return False
                elif isinstance(val, (tuple, list)):
                    new_folder = os.path.relpath(os.path.join(root, key))
                    if setup_obj is None:
                        write_directory = True
                    else:
                        write_directory = setup_obj.on_create_folder(new_folder)
                    if write_directory:
                        pinfo(f'Creating folder: {new_folder}')
                        try:
                            os.makedirs(new_folder, exist_ok=True)
                            final_inner_value = {}
                            for val_ in val:
                                if isinstance(val_, (dict, OrderedDict)):
                                    for key_ in val_.keys():
                                        if key_ in final_inner_value.keys():
                                            pwarn(f'Can not create duplicate folder {key_} inside {new_folder}')
                                            return False
                                    final_inner_value.update(val_)
                            if not Actions.expand_file_structure(new_folder, final_inner_value, setup_obj, constants):
                                return False
                        except (OSError, FileNotFoundError, NotADirectoryError) as e:
                            perror(f'Could not create folder - {type(e).__name__}:{e}')
                            return False
        return True

    @staticmethod
    def is_forbidden_import(code_obj: ast.Import):
        if code_obj.names[0].name.startswith(__module__):
            return True
        elif code_obj.names[0].asname is not None:
            try:
                eval(f'lambda: {code_obj.names[0].asname}')()
                return True
            except NameError:
                pass
        return False
    
    @staticmethod
    def is_forbidden_importfrom(code_obj: ast.ImportFrom, action_name: str):
        if code_obj.module == __module__:
            if code_obj.names[0].name not in ['Setup', 'DefaultSetup']: # + \
                # (['DefaultSetup'] if action_name == 'default' else []):
                return True
            elif code_obj.names[0].asname is not None:
                try:
                    eval(f'lambda: {code_obj.names[0].asname}')()
                    return True
                except NameError:
                    pass
        elif code_obj.module.startswith(__module__):
            return True
        elif code_obj.names[0].asname is not None:
            try:
                eval(f'lambda: {code_obj.names[0].asname}')()
                return True
            except NameError:
                pass
        return False

    @staticmethod
    def build(structure, action_name, tasks):
        if not os.path.isfile(structure):
            perror(f'Could not find the project-structure.yaml file, given {structure}')
            return False
        else:
            with open(structure) as f:
                try:
                    yaml_data = yaml.load(f, Loader=FullLoader)
                except yaml.scanner.ScannerError as e:
                    perror(f"{type(e).__name__} -> {e}")
                    return False
            project_name = yaml_data.get('project-name')
            working_dir = yaml_data.get('working-dir')
            if not isinstance(project_name, str) or not isinstance(working_dir, str):
                pwarn(f'Could not find valid data for "project-name" and "working-dir" inside {structure}')
                return False
            try:
                envionment = yaml_data.get('environment', {})
                if envionment is not None:
                    if not isinstance(envionment, (dict, OrderedDict)):
                        raise TypeError(f'Invalid environment variables in "{structure}"')
                    for env_key, env_val in envionment.items():
                        pinfo(f'Adding environment variable "{env_key.strip()}": {env_val}')
                        os.environ[env_key.strip()] = env_val

                __constants = yaml_data.get('constants', {})
                __constants__ = dict()
                if __constants is not None:
                    if not isinstance(__constants, (dict, OrderedDict)):
                        raise TypeError(f'Invalid constant variables in "{structure}"')
                    for const_key, const_val in __constants.items():
                        if re.match(r'^[a-z_][a-z0-9_]*$', const_key.strip(), flags=re.I):
                            pinfo(f'Adding constant variable "{const_key.strip()}": {const_val}')
                            __constants__[const_key.strip()] = const_val
                        else:
                            raise KeyError(f'Could not create constant variable "{const_key.strip()}"')
                    constants = type('Constants', (object, ), {
                        key : Constant(val) for key, val in __constants__.items()
                    })
                else:
                    constants = None

                if action_name in yaml_data['boilerplates'].keys():
                    action = yaml_data['boilerplates'][action_name]
                else:
                    raise KeyError(f'Could not find the boilerplate structure for action "{action_name}"')
                setup_code = action.get('setup')
                setup_obj = None
                class_def_line_no = 0
                if setup_code is not None:
                    if not isinstance(setup_code, str):
                        raise TypeError(f'setup_code should be a valid python source code in action "{action_name}"')
                    else:
                        source_code_tree = ast.parse(setup_code)
                        setup_class_name = f'{action_name.strip().title()}Setup'
                        actual_source = ''
                        for code_obj in source_code_tree.body:
                            if isinstance(code_obj, ast.Import):
                                if not Actions.is_forbidden_import(code_obj):
                                    actual_source += f'\n{ast.get_source_segment(setup_code, code_obj)}'
                                else:
                                    raise ImportError(f'Forbidden import at line {code_obj.lineno} -> ' +
                                        f'"{ast.get_source_segment(setup_code, code_obj)}"')
                            elif isinstance(code_obj, ast.ImportFrom):
                                if not Actions.is_forbidden_importfrom(code_obj, action_name):
                                    actual_source += f'\n{ast.get_source_segment(setup_code, code_obj)}'
                                else:
                                    raise ImportError(f'Forbidden import at line {code_obj.lineno} -> ' +
                                        f'"{ast.get_source_segment(setup_code, code_obj)}"')
                            elif isinstance(code_obj, ast.ClassDef):
                                if code_obj.name == setup_class_name:
                                    # print(code_obj.bases[0].id)
                                    # if 'Setup' in [base.id for base in code_obj.bases]:
                                    #     actual_source += f'\n\n{ast.get_source_segment(setup_code, code_obj)}'
                                    # else:
                                    #     raise SyntaxWarning(f'Setup class "{code_obj.name}" at line {code_obj.lineno} '+
                                    #         'must inherit from "any_project.Setup" class')
                                    actual_source += f'\n\n{ast.get_source_segment(setup_code, code_obj)}'
                                    class_def_line_no = code_obj.lineno
                                else:
                                    raise SyntaxWarning(f'Forbidden class definition at line {code_obj.lineno} ->' +
                                        f' "{code_obj.name}"')
                            else:
                                raise SyntaxWarning(f'Invalid code definition at line {code_obj.lineno}')

                    exec(actual_source, globals())
                    SetupClass = eval(setup_class_name)
                    if not issubclass(SetupClass, Setup):
                        raise SyntaxWarning(f'Setup class "{setup_class_name}" at line {class_def_line_no} '+
                            'must inherit from "any_project.Setup" class')
                    # setup_obj = eval(f'{setup_class_name}(constants)')
                    setup_obj = SetupClass(constants)
                    setup_obj.do_pre_validations()
                    setup_obj.set_prompts()
                    for task in (tasks.split(';') if tasks is not None else []):
                        setup_obj.do_task_on(task=task)

                git_commit = action.get('git-commit')
                if not isinstance(git_commit, str):
                    if git_commit is not None:
                        pwarn(f'Value of "git-commit" under "{action}" should be a string')
                    git_commit = None

                structure_ = action.get('structure', {})
                if structure_ is not None:
                    if not isinstance(structure_, (dict, OrderedDict)):
                        raise TypeError(f'Invalid file structure_ for action "{action_name}"')
                    else:
                        # print(structure)
                        working_dir = os.path.relpath(working_dir)
                        root = os.path.relpath(os.path.join(working_dir, project_name))
                        os.makedirs(root, exist_ok=True)
                        if not Actions.expand_file_structure(root, structure_, setup_obj, constants):
                            shutil.rmtree(root)
                            return False
                        else:
                            try:
                                is_git_repo = constants.git_repo
                                if not isinstance(is_git_repo, bool):
                                    is_git_repo = False
                            except AttributeError:
                                is_git_repo = False
                            if is_git_repo:
                                if git_commit is not None:
                                    success, exc = Actions.init_and_commit_git_repo(root, git_commit)
                                    if not success:
                                        perror(f"{type(exc).__name__} -> {exc}")
                if setup_obj is not None:
                    setup_obj.do_post_validations()                    
            except (KeyError, TypeError) as e:
                perror(f"{type(e).__name__} -> {e}")
                return False
        return True

    @staticmethod
    def main():
        parser = ArgumentParser(prog=__program__,
            description='A python based cli tool to create computer file structure or project structure from a `yaml` input.')
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('-init', action='store', type=str, default=None, help='Initialize a project')
        group.add_argument('-build', action='store', type=str, default=None, help='Build a project from a initialized yaml code')
        parser.add_argument('-v', action='version', version='%(prog)s - ' + __version__)
        parser.add_argument('-version', action='version', version=__version__)
        results = parser.parse_args()

        if results.init is not None:
            pattern = r'^([^\:]+)(?:\:([a-z0-9_][a-z0-9_\-]*))?$'
            m = re.match(pattern, results.init.strip(), flags=re.IGNORECASE)
            if m is None:
                parser.error('argument value of `-init` is invalid')
            else:
                target_dir, project_name = m.groups()
            target_dir = os.path.abspath(target_dir)
            project_name = re.sub(r'[^a-z0-9_\-]', '_', os.path.basename(target_dir), flags=re.IGNORECASE) \
                if project_name is None else project_name
            project_structure_yaml = Actions.init(target_dir, project_name)
            if project_structure_yaml is None :
                perror('Could not initialize project structure.')
                exit(-1)
            else:
                pinfo(f'Project structure created at "{project_structure_yaml}"')
        else:
            pattern = r'^([^\:\?]+)(?:\:([a-z_][a-z0-9_]*))?(?:\?((?:[a-z_][a-z_0-9]*)(?:\;[a-z_][a-z0-9_]*)*))?$'
            m = re.match(pattern, results.build.strip(), flags=re.IGNORECASE)
            if m is None:
                parser.error('argument value of `-build` is invalid')
            else:
                target_dir, action_name, tasks = m.groups()
                if action_name is None:
                    action_name = 'default'
            target_dir = os.path.abspath(target_dir)
            value = os.path.join(target_dir, 'project-structure.yaml')
            Actions.build(value, action_name, tasks)

# print(locals())