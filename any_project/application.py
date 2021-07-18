from any_project import __module__
from any_project import Setup
from any_project.template import yaml_template
from any_project.constant import Constant
from any_project.internal import InternalActions
from collections import OrderedDict
from yaml.loader import FullLoader
import oyaml as yaml
from pymsgprompt.logger import pinfo, perror, pwarn
from pymsgprompt.prompt import ask
import os, re, ast


class Actions(object):
    @staticmethod
    def init(target_dir, project_name, template_generator=None):
        YAML_CODE_DICT = yaml_template(project_name,
            os.path.relpath(target_dir), template_generator)
        try:
            os.makedirs(target_dir, exist_ok=True)
        except FileNotFoundError as e:
            perror(f"{type(e).__name__} -> {e}")
            return None
        project_structure_yaml = os.path.join(target_dir, 'project-structure.yaml')
        overwrite_option = None
        if os.path.isfile(project_structure_yaml):
            overwrite_option = ask('Do you want to overwrite the existing project structure?', \
                choices=['yes', 'no'], default='no', on_error=lambda *argv: True)
        else:
            overwrite_option = 'yes'
        if overwrite_option == 'yes':
            with open(project_structure_yaml, 'w') as f:
                yaml.dump(YAML_CODE_DICT, f, indent=4)
        else:
            pwarn('Action has been prevented by user!')
            return None
        return project_structure_yaml
        
    @staticmethod
    def build(structure, action_name, tasks, delete_backup_on_success=None):
        backup_zip = None
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
                pwarn('Could not find valid data for "project-name" and "working-dir" ' +
                    f'inside {structure}')
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
                working_dir = os.path.relpath(working_dir)
                root = os.path.relpath(os.path.join(working_dir, project_name))
                
                backup_zip = InternalActions.take_safe_backup(working_dir, project_name)

                if action_name in yaml_data['boilerplates'].keys():
                    action = yaml_data['boilerplates'][action_name]
                else:
                    raise KeyError('Could not find the boilerplate structure ' +
                        f'for action "{action_name}"')
                setup_code = action.get('setup')
                setup_obj = None
                class_def_line_no = 0
                if setup_code is not None:
                    if not isinstance(setup_code, str):
                        raise TypeError('setup_code should be a valid python source ' +
                            f'code in action "{action_name}"')
                    else:
                        source_code_tree = ast.parse(setup_code)
                        setup_class_name = f'{action_name.strip().title()}Setup'
                        actual_source = ''
                        for code_obj in source_code_tree.body:
                            if isinstance(code_obj, ast.Import):
                                if not InternalActions.is_forbidden_import(code_obj):
                                    actual_source += f'\n{ast.get_source_segment(setup_code, code_obj)}'
                                else:
                                    raise ImportError(f'Forbidden import at line {code_obj.lineno} -> ' +
                                        f'"{ast.get_source_segment(setup_code, code_obj)}"')
                            elif isinstance(code_obj, ast.ImportFrom):
                                if not InternalActions.is_forbidden_importfrom(code_obj):
                                    actual_source += f'\n{ast.get_source_segment(setup_code, code_obj)}'
                                else:
                                    raise ImportError(f'Forbidden import at line {code_obj.lineno} -> ' +
                                        f'"{ast.get_source_segment(setup_code, code_obj)}"')
                            elif isinstance(code_obj, ast.ClassDef):
                                if code_obj.name == setup_class_name:
                                    actual_source += f'\n\n{ast.get_source_segment(setup_code, code_obj)}'
                                    class_def_line_no = code_obj.lineno
                                else:
                                    raise SyntaxWarning('Forbidden class definition at line ' +
                                        f'{code_obj.lineno} -> "{code_obj.name}"')
                            else:
                                raise SyntaxWarning(f'Invalid code definition at line {code_obj.lineno}')

                    exec(actual_source, globals())
                    SetupClass = eval(setup_class_name)
                    if not issubclass(SetupClass, Setup):
                        raise SyntaxWarning(f'Setup class "{setup_class_name}" ' +
                            f'at line {class_def_line_no} '+
                            'must inherit from "any_project.Setup" class')
                    setup_obj = SetupClass(action_name)
                    setup_obj.pre_validations()
                    setup_obj.set_prompts()
                    for task in (tasks.split(';') if tasks is not None else []):
                        setup_obj.on_task(task=task)

                structure_ = action.get('structure', {})
                if structure_ is not None:
                    if not isinstance(structure_, (dict, OrderedDict)):
                        raise TypeError(f'Invalid file structure_ for action "{action_name}"')
                    else:
                        if not os.path.isdir(root):
                            pinfo(f'Creating ROOT directory: "{root}"')
                        os.makedirs(root, exist_ok=True)
                        if not InternalActions.expand_file_structure( \
                            root, structure_, setup_obj, constants):
                            InternalActions.restore_safe_backup( \
                                root, working_dir, backup_zip)
                            return False
                        else:
                            git_commit = action.get('git-commit')
                            try:
                                is_git_repo = constants.git_repo
                                if not isinstance(is_git_repo, bool): is_git_repo = False
                            except AttributeError:
                                is_git_repo = False
                            if not isinstance(git_commit, str):
                                if git_commit is None and action_name.strip() == 'default':
                                    git_commit = 'Initial commit'
                                else:
                                    if is_git_repo:
                                        pwarn(f'Value of "git-commit" under "{action_name}"' +
                                            ' should be a string')
                                    git_commit = None
                            if is_git_repo and git_commit is not None:
                                success, exc = InternalActions.add_git_commit(root, git_commit)
                                if not success:
                                    perror(f"{type(exc).__name__} -> {exc}")
                if setup_obj is not None:
                    setup_obj.post_validations()                    
            except (KeyError, TypeError) as e:
                perror(f"{type(e).__name__} -> {e}")
                return False
        if delete_backup_on_success is None \
            and backup_zip is not None and os.path.isfile(backup_zip):
            should_delete_backup = ask('Do you want to delete the backup zip?', \
                choices=['yes', 'no'], default='no', on_error=lambda *argv: True)
            delete_backup_on_success = should_delete_backup == 'yes'
        else:
            delete_backup_on_success = False
        if delete_backup_on_success:
            pinfo(f'Deleting backup "{backup_zip}"')
            try:
                os.unlink(backup_zip)
            except (FileNotFoundError, PermissionError) as e:
                perror(f'{type(e).__name__} occurred -> {e}')
                pwarn(f'Could not delete the backup "{backup_zip}"')
        return True
