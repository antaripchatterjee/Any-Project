from any_project import __module__
from any_project import Setup
from any_project.template import yaml_template
from any_project.constant import Constant
from collections import OrderedDict
from zipfile import ZipFile
from yaml.loader import FullLoader
import oyaml as yaml
from pymsgprompt.logger import pinfo, perror, pwarn
from pymsgprompt.prompt import ask
import os, re, ast, shutil, glob, git, tempfile


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
    def init_and_commit_git_repo(root, msg):
        try:
            try:
                repo = git.Repo(root)
            except git.exc.InvalidGitRepositoryError:
                pinfo('Initializing as a git repo')
                repo = git.Repo.init(root)
            git_ignore = os.path.relpath(
                os.path.join(root, '.gitignore')
            )
            if not os.path.isfile(git_ignore):
                pinfo('Creating a git ignore file')
                open(git_ignore, 'w').close()
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
    def is_forbidden_importfrom(code_obj: ast.ImportFrom):
        if code_obj.module == __module__:
            if code_obj.names[0].name not in ['Setup', 'DefaultSetup']:
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
                try:
                    actual_cwd = os.getcwd()
                    os.chdir(working_dir)
                    files_to_add_in_backup_zip = [_file_to_add_in_backup_zip \
                        for _file_to_add_in_backup_zip in glob.glob(os.path.relpath(\
                            os.path.join(project_name, '**')), recursive=True) \
                                + glob.glob(os.path.relpath(os.path.join(project_name, '.*')), \
                                    recursive=True) if os.path.exists(_file_to_add_in_backup_zip) and \
                                        os.path.abspath(_file_to_add_in_backup_zip) != \
                                            os.path.abspath(os.path.join(project_name, '.git'))]

                    if len(files_to_add_in_backup_zip) > 0:
                        os.makedirs(os.path.relpath('backups'), exist_ok=True)
                        backup_zip = tempfile.mkstemp(suffix='.zip', prefix=f'backup-{project_name}-', \
                            dir=os.path.relpath('backups'))[1]

                        with ZipFile(backup_zip, 'w') as zip:
                            for file_to_add_in_backup_zip in files_to_add_in_backup_zip:
                                zip.write(file_to_add_in_backup_zip)
                        pinfo(f'Created backup zip file at "{backup_zip}"')
                    else:
                        pinfo('No files or folders found, ignoring backup process')
                        backup_zip = "<Empty/>"
                except Exception as e:
                    perror(f"{type(e).__name__} occurred -> {e}")
                    backup_zip = None
                finally:
                    os.chdir(actual_cwd)

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
                                if not Actions.is_forbidden_import(code_obj):
                                    actual_source += f'\n{ast.get_source_segment(setup_code, code_obj)}'
                                else:
                                    raise ImportError(f'Forbidden import at line {code_obj.lineno} -> ' +
                                        f'"{ast.get_source_segment(setup_code, code_obj)}"')
                            elif isinstance(code_obj, ast.ImportFrom):
                                if not Actions.is_forbidden_importfrom(code_obj):
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
                    # setup_obj = eval(f'{setup_class_name}(constants)')
                    setup_obj = SetupClass(constants)
                    setup_obj.pre_validations()
                    setup_obj.set_prompts()
                    for task in (tasks.split(';') if tasks is not None else []):
                        setup_obj.on_task(task=task)

                structure_ = action.get('structure', {})
                if structure_ is not None:
                    if not isinstance(structure_, (dict, OrderedDict)):
                        raise TypeError(f'Invalid file structure_ for action "{action_name}"')
                    else:
                        # print(structure)
                        pinfo(f'Creating ROOT directory: "{root}"')
                        os.makedirs(root, exist_ok=True)
                        if not Actions.expand_file_structure(root, structure_, setup_obj, constants):
                            if backup_zip is not None:
                                if backup_zip != '<Empty/>':
                                    for _file_or_dir in [_dir for _dir in os.listdir(root)\
                                        if _dir != '.git']:
                                        try:
                                            shutil.rmtree(os.path.relpath(os.path.join(root, \
                                                _file_or_dir)))
                                        except NotADirectoryError:
                                            os.unlink(os.path.relpath(os.path.join(root, \
                                                _file_or_dir)))
                                        except PermissionError as e:
                                            pwarn(f"{type(e).__name__} occurred -> {e}")
                                    actual_cwd = os.getcwd()
                                    try:
                                        os.chdir(working_dir)
                                        print(f'Backing up from "{backup_zip}"')
                                        with ZipFile(backup_zip, 'r') as zip:
                                            zip.printdir()
                                            zip.extractall()
                                    except Exception as e:
                                        perror(f"Error occured while taking backup, {type(e).__name__} -> {e}")
                                    finally:
                                        os.chdir(actual_cwd)
                            else:
                                pwarn('Could not find any backup!')
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
                                success, exc = Actions.init_and_commit_git_repo(root, git_commit)
                                if not success:
                                    perror(f"{type(exc).__name__} -> {exc}")
                if setup_obj is not None:
                    setup_obj.post_validations()                    
            except (KeyError, TypeError) as e:
                perror(f"{type(e).__name__} -> {e}")
                return False
        return True
