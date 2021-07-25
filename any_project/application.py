from any_project import __module__
from any_project import Setup
from any_project.template import yaml_template
from any_project.constant import Constant
from any_project.internal import BuildActionData, InternalActions
from collections import OrderedDict
import oyaml as yaml
from pymsgprompt.logger import pinfo, perror, pwarn
from pymsgprompt.prompt import ask
import os, re
from any_project.setup import ValidationError
from any_project.setup import ValidationResult


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
    @InternalActions.post_build_activity
    def build(structure, action_name, tasks, delete_backup=None):
        # Complete the precheck before building the structure project
        precheck_result = InternalActions.any_project_precheck(structure)
        if precheck_result is None:
            return BuildActionData(status=False)
        
        # Initialize the local variables
        yaml_data, working_dir, project_name = precheck_result
        backup_zip, root = None, None
        
        # Load the environment variables
        try:
            envionment = yaml_data.get('environment')
            if envionment is not None:
                if not isinstance(envionment, (dict, OrderedDict)):
                    raise TypeError(f'Invalid data of "environment" inside "{structure}"')
                pinfo('Adding environment variables')
                os.environ.update({
                    env_key.strip() : env_val \
                        for env_key, env_val in envionment.items()
                })
        except TypeError as e:
            perror(f'{e}')
            return BuildActionData(status=False)

        # Load the any-project constants
        try:
            temp_constants = yaml_data.get('constants')
            if temp_constants is None:
                constants = type('Constants', (object, ), {})
            else:
                if not isinstance(temp_constants, (dict, OrderedDict)):
                    raise TypeError(f'Invalid data of constants inside "{structure}"')
                def invalid_constant(key):
                    raise KeyError(f'Invalid any-project constant {key}')
                def valid_constant(key, val):
                    pinfo(f'Adding any-project constant "{key}={val}"')
                    return Constant(val)
                k_pat = r'^[a-z_][a-z0-9_]*$'
                constants = type('Constants', (object, ), {
                    key.strip() : valid_constant(key.strip(), val) \
                        if re.match(k_pat, key.strip(), flags=re.I) \
                            else invalid_constant(key.strip()) \
                                for key, val in temp_constants.items()              
                })
        except (TypeError, KeyError) as e:
            perror(f'{e}')
            return BuildActionData(status=False)
        
        # Get the project root path
        root = os.path.relpath(os.path.join(working_dir, project_name))
        
        # Take the safety backup
        backup_zip, error_occured = InternalActions.take_safe_backup(
            working_dir, project_name
        )
        if error_occured:
            if backup_zip is not None:
                pinfo('Deleting corrupted safety backup')
                os.unlink(backup_zip)
            return BuildActionData(
                status=False,
                root=root,
                cwd=working_dir,
                backup_zip=None,
                delete_backup=False
            )
        
        # Get the action's architecture
        action = None
        setup_obj = None
        try:
            if action_name in yaml_data['boilerplates'].keys():
                action = yaml_data['boilerplates'][action_name]
            else:
                raise KeyError(f'Could not find the action "{action_name}"')
        except KeyError as e:
            perror(f'{type(e).__name__} occurred -> {e}')
            return BuildActionData(
                status=False,
                root=root,
                cwd=working_dir,
                backup_zip=backup_zip,
                delete_backup=delete_backup
            )
        
        # Get the setup code from yaml
        setup_code = action.get('setup')
        if setup_code is not None:
            # Validation of setup code
            if not isinstance(setup_code, str):
                perror(f'Invalid setup code in action "{action_name}"')
                pinfo('Setup code should be a valid python code')
                return BuildActionData(
                    status=False,
                    root=root,
                    cwd=working_dir,
                    backup_zip=backup_zip,
                    delete_backup=delete_backup
                )

            # Get the source code, class name and it's location 
            # in terms of line number in the source code
            try:
                actual_source, setup_class_name, class_def_line_no = \
                    InternalActions.get_setup_source_code(
                        setup_code, action_name
                    )
            except (SyntaxError, ImportError) as e:
                perror(f'{e}')
                return BuildActionData(
                    status=False,
                    root=root,
                    cwd=working_dir,
                    backup_zip=backup_zip,
                    delete_backup=delete_backup
                )

            # Execute the setup source code and create object
            # of the setup class of the action
            try:
                exec(actual_source, globals())
                SetupClass = eval(setup_class_name)
                if not issubclass(SetupClass, Setup):
                    raise SyntaxError(
                        f'Setup class "{SetupClass.__name__}" ' + \
                            f'at line {class_def_line_no} '+ \
                                'must inherit from "any_project.Setup" class'
                    )

                # Creating object of the setup class
                setup_obj = SetupClass(action_name)

                # Completing the pre-validations of the setup
                try:
                    result = setup_obj.pre_validation()
                except Exception as e:
                    raise RuntimeError(
                        f'<{type(e).__name__}> {e}, while executing' + \
                            'pre_validation()')

                if not isinstance(result, ValidationResult):
                    result = ValidationResult(
                        False, 'Illegal type of pre-validation result.'
                    )
                if not result.successful:
                    raise ValidationError(result.message)
                
                # Asking the prompt value from the user
                try:
                    setup_obj.set_prompts()
                except Exception as e:
                    raise RuntimeError(
                        f'<{type(e).__name__}> {e}, while executing ' + \
                            'set_prompts()')

                # Executing all the tasks
                for task in tasks:
                    try:
                        setup_obj.on_task(task=task)
                    except Exception as e:
                        raise RuntimeError(
                            f'<{type(e).__name__}> {e}, while executing' + \
                                f'on_task(task="{task}")')
            except (SyntaxError, ValidationError, RuntimeError) as e:
                # Handling RuntimeError is important to prevent any
                # mess up of the code, after the setup functions
                # get any exception
                perror(f'{type(e).__name__} occurred -> {e}')
                return BuildActionData(
                    status=False,
                    root=root,
                    cwd=working_dir,
                    backup_zip=backup_zip,
                    delete_backup=delete_backup
                )

        # Get the structure from yaml
        structure_ = action.get('structure')
        if structure_ is not None:
            if not isinstance(structure_, (dict, OrderedDict)):
                perror(f'Invalid file structure in action "{action_name}"')
                return BuildActionData(
                    status=False,
                    root=root,
                    cwd=working_dir,
                    backup_zip=backup_zip,
                    delete_backup=delete_backup
                )
            
            # Creating the ROOT directory if does not exist
            if not os.path.isdir(root):
                pinfo(f'Creating ROOT directory: "{root}"')
            os.makedirs(root, exist_ok=True)

            # Expand the file structure
            if not InternalActions.expand_file_structure( \
                root, structure_, setup_obj, constants):
                perror('Could not expand the file structure!')
                return BuildActionData(
                    status=False,
                    root=root,
                    cwd=working_dir,
                    backup_zip=backup_zip,
                    delete_backup=delete_backup
                )
            
            # Git repo functionality
            try:
                is_git_repo = constants.git_repo
                if not isinstance(is_git_repo, bool):
                    is_git_repo = False
            except AttributeError:
                is_git_repo = False

            # Get the git commit message
            git_commit = action.get('git-commit')
        
            if not isinstance(git_commit, str):
                # Handle invalid value of git-commit
                if git_commit is None and \
                    action_name.strip() == 'default':
                    git_commit = 'Commit for default action'
                else:
                    if is_git_repo:
                        pwarn(
                            f'Value of "git-commit" under ' + \
                                f'"{action_name}" action should be a string'
                        )
                    git_commit = None
            if is_git_repo and git_commit is not None:
                git_commit = os.path.expandvars(git_commit).format(
                    prompts = None if setup_obj \
                        is None else setup_obj.prompts,
                    consts = constants
                )

                # Create a git repo if does not exist
                # and add the files with a commit message
                exc = InternalActions.add_git_commit(
                    root, git_commit
                )
                if exc is not None:
                    perror(f"{type(exc).__name__} occurred -> {exc}")
                    pwarn('Commit may not be occurred successfully!')
                    # Even if git commit is failed, it should not be 
                    # rolled back. If rolling back is necessary, it
                    # can be done using post-validation

        # Do the post build validations
        if setup_obj is not None:
            try:
                try:
                    result = setup_obj.post_validation()
                except Exception as e:
                    raise RuntimeError(
                        f'<{type(e).__name__}> {e}, while executing ' + \
                            'post_validtion()')
                if not isinstance(result, ValidationResult):
                    result = ValidationResult(
                        False, 'Illegal type of post-validation result.'
                    )
                if not result.successful:
                    raise ValidationError(result.message)
            except (ValidationError, RuntimeError) as e:
                perror(f'{type(e).__name__} occurred -> {e}')
                return BuildActionData(
                    status=False,
                    root=root,
                    cwd=working_dir,
                    backup_zip=backup_zip,
                    delete_backup=delete_backup
                )

        return BuildActionData(
            status=True,
            root=root,
            cwd=working_dir,
            backup_zip=backup_zip,
            delete_backup=delete_backup 
        )
