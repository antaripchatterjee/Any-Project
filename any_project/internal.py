from any_project import __module__
from collections import OrderedDict
from pymsgprompt.logger import pinfo, perror, pwarn
from pymsgprompt.prompt import ask
import os, re, ast, git, glob, tempfile, shutil
from zipfile import ZipFile
from zipfile import BadZipFile
from yaml.loader import FullLoader
from yaml.scanner import ScannerError
import oyaml as yaml
from functools import wraps

class BuildActionData:
    def __init__(self, **kwargv):
        self.__root = kwargv.get('root')
        self.__cwd = kwargv.get('cwd')
        self.__status = kwargv.get('status')
        self.__backup_zip = kwargv.get('backup_zip')
        self.__delete_backup = kwargv.get('delete_backup')
    
    @property
    def root(self) : return self.__root

    @property
    def cwd(self) : return self.__cwd

    @property
    def status(self) : return self.__status

    @property
    def backup_zip(self) : return self.__backup_zip

    @property
    def delete_backup(self) : return self.__delete_backup


class InternalActions(object):
    @staticmethod
    def add_git_commit(root, msg):
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

        try:
            pinfo('Git add all')
            repo.git.add(A=True)
            pinfo(f'Git Commit Message:"{msg}"')
            repo.git.commit(m=msg)
            return None
        except Exception as e:
            return e

    @staticmethod
    def get_overwriting_content(filename, lineno, overwriting_content, force_overwrite):
        existing_file_lines = open(filename).read().split('\n')
        overwriting_lines = overwriting_content.split('\n')
        
        if lineno == 0: lineno = len(existing_file_lines) + 1

        if existing_file_lines[abs(lineno)-1:abs(lineno)+len(overwriting_lines)-1] \
            == overwriting_lines and not force_overwrite: return None

        # If lineno is negative, update the line
        # Else if lineno is positive, insert the line
        # Else if lineno is 0, append the content

        if lineno < 0:
            # Update
            lineno = abs(lineno)
            if lineno <= len(existing_file_lines):
                overwriting_file_lines = existing_file_lines[:lineno-1] + \
                    overwriting_lines + existing_file_lines[lineno+len(overwriting_lines)-1:]
            else:
                overwriting_file_lines = existing_file_lines + \
                    [0]*(lineno-len(existing_file_lines)-1) + overwriting_lines
        else:
            # Insert
            if lineno <= len(existing_file_lines):
                overwriting_file_lines = existing_file_lines[:lineno-1] + \
                    overwriting_lines + existing_file_lines[lineno-1:]
            else:
                overwriting_file_lines = existing_file_lines + \
                    [0]*(lineno-len(existing_file_lines)-1) + overwriting_lines
        return '\n'.join(overwriting_file_lines)

    @staticmethod
    def expand_file_structure(root, structure, setup_obj, constants):
        for key, val in structure.items():
            key = key.strip()
            source = ''
            m = re.match(r'^\$(env|prompt|const)\:([^\s].*)$', key, \
                flags=re.IGNORECASE)
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
            try:
                if isinstance(val, str):
                    _pat_i = r'\/\\\*\?\:\"\<\>\|'
                    pattern = r'^([^\s{0}][^\/\\\*\?\:\"\<\>\|]+[^\s{0}])(?:\s*\:([\+\-]?[\d]+)([fF])?)?$'.format(_pat_i)
                    m = re.match(pattern, key)
                    try:
                        filename, lineno, force_overwrite = m.groups()
                    except AttributeError:
                        perror(f'Issue found with filename, invalid key "{key}"')
                        return False
                    next_file = os.path.relpath(os.path.join(root, filename))
                    if setup_obj is None:
                        write_file = True
                    else:
                        try:
                            write_file = setup_obj.on_create_file(next_file)
                        except Exception as e:
                            raise RuntimeError(
                                f'<{type(e).__name__}> {e}, while executing ' + \
                                    f'on_create_file(filename="{next_file}")'
                            )
                    if write_file:
                        if os.path.isfile(next_file):
                            pinfo(f'Overwriting file : {next_file}')
                            overwriting = True
                        else:
                            pinfo(f'Creating file  : {next_file}')
                            overwriting = False
                        try:
                            content = os.path.expandvars(val).format(
                                prompts = None if setup_obj is None else setup_obj.prompts,
                                consts = constants
                            )

                            # If lineno is None, then overwrite completely
                            if overwriting and lineno is not None:
                                content = InternalActions.get_overwriting_content(
                                    next_file, int(lineno), content, force_overwrite
                                )
                            if content is not None:
                                with open(next_file, 'w') as f:
                                    f.write(content)

                        except (OSError, FileNotFoundError, NotADirectoryError) as e:
                            perror(f'Could not create file - {type(e).__name__}:{e}')
                            return False
                        except (KeyError, AttributeError) as e:
                            pwarn(f'{type(e).__name__} occurred while writing the file')
                            perror(f"Message: {e}")
                            return False
                elif val is None:
                    new_folder = os.path.relpath(os.path.join(root, key))
                    if setup_obj is None:
                        write_directory = True
                    else:
                        try:
                            write_directory = setup_obj.on_create_folder(new_folder)
                        except Exception as e:
                            raise RuntimeError(
                                f'<{type(e).__name__}> {e}, while executing ' + \
                                    f'on_create_folder(directory="{new_folder}")'
                            )
                    if write_directory:
                        if not os.path.isdir(new_folder):
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
                        try:
                            write_directory = setup_obj.on_create_folder(new_folder)
                        except Exception as e:
                            raise RuntimeError(
                                f'<{type(e).__name__}> {e}, while executing ' + \
                                    f'on_create_folder(directory="{new_folder}")'
                            )
                    if write_directory:
                        if not os.path.isdir(new_folder):
                            pinfo(f'Creating folder: {new_folder}')
                        try:
                            os.makedirs(new_folder, exist_ok=True)
                            if not InternalActions.expand_file_structure(\
                                new_folder, val, setup_obj, constants):
                                return False
                        except (OSError, FileNotFoundError, NotADirectoryError) as e:
                            perror(f'Could not create folder - {type(e).__name__}:{e}')
                            return False
                elif isinstance(val, (tuple, list)):
                    new_folder = os.path.relpath(os.path.join(root, key))
                    if setup_obj is None:
                        write_directory = True
                    else:
                        try:
                            write_directory = setup_obj.on_create_folder(new_folder)
                        except Exception as e:
                            raise RuntimeError(
                                f'<{type(e).__name__}> {e}, while executing ' + \
                                    f'on_create_folder(directory="{new_folder}")'
                            )
                    if write_directory:
                        if not os.path.isdir(new_folder):
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
                            if not InternalActions.expand_file_structure(
                                new_folder, final_inner_value, setup_obj, constants):
                                return False
                        except (OSError, FileNotFoundError, NotADirectoryError) as e:
                            perror(f'Could not create folder - {type(e).__name__}:{e}')
                            return False
            except RuntimeError as e:
                perror(f'{type(e).__name__} occurred -> {e}')
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
    def any_project_precheck(structure):
        if not os.path.isfile(structure):
            perror(f'Could not find the project-structure.yaml file, given {structure}')
            return None
        else:
            with open(structure) as f:
                try:
                    yaml_data = yaml.load(f, Loader=FullLoader)
                except ScannerError as e:
                    perror(f"{type(e).__name__} -> {e}")
                    return None
            project_name = yaml_data.get('project-name')
            working_dir = yaml_data.get('working-dir')
            if not isinstance(project_name, str) or not isinstance(working_dir, str):
                perror('Invalid data of "project-name" and "working-dir" inside {structure}')
                return None
            else:
                working_dir = os.path.abspath(working_dir)
                if not os.path.isdir(working_dir):
                    perror(f'Invalid working-dir: {working_dir} inside {structure}')
                    return None
        return yaml_data, working_dir, project_name
            
    @staticmethod
    def get_setup_source_code(setup_code, action_name):
        source_code_tree = ast.parse(setup_code)
        setup_class_name = f'{action_name.strip().title()}Setup'
        actual_source = ''
        class_def_line_no = None
        for code_obj in source_code_tree.body:
            if isinstance(code_obj, ast.Import):
                if not InternalActions.is_forbidden_import(code_obj):
                    actual_source += f'\n{ast.get_source_segment(setup_code, code_obj)}'
                else:
                    raise ImportError(
                        f'Forbidden import -> {code_obj.lineno}:' + \
                            ast.get_source_segment(setup_code, code_obj)
                    )
            elif isinstance(code_obj, ast.ImportFrom):
                if not InternalActions.is_forbidden_importfrom(code_obj):
                    actual_source += f'\n{ast.get_source_segment(setup_code, code_obj)}'
                else:
                    raise ImportError(
                        f'Forbidden import -> {code_obj.lineno}:' + \
                            ast.get_source_segment(setup_code, code_obj)
                    )
            elif isinstance(code_obj, ast.ClassDef):
                if code_obj.name == setup_class_name:
                    actual_source += \
                        f'\n\n{ast.get_source_segment(setup_code, code_obj)}'
                    class_def_line_no = code_obj.lineno
                else:
                    raise SyntaxError(
                        'Forbidden class definition at line ' +
                            f'{code_obj.lineno} -> "{code_obj.name}"'
                    )
            else:
                raise SyntaxError(
                    f'Invalid code definition at line {code_obj.lineno}'
                )
        return actual_source, setup_class_name, class_def_line_no

    @staticmethod
    def take_safe_backup(working_dir, project_name):
        backup_zip = None
        try:
            actual_cwd = os.getcwd()
            os.chdir(working_dir)
            files_to_add_in_backup_zip = [_file_to_add_in_backup_zip \
                for _file_to_add_in_backup_zip in glob.glob(os.path.relpath( \
                    os.path.join(project_name, '**')), recursive=True) \
                        + glob.glob(os.path.relpath(os.path.join(project_name, '.*')), \
                            recursive=True) if os.path.exists(_file_to_add_in_backup_zip) and \
                                os.path.abspath(_file_to_add_in_backup_zip) != \
                                    os.path.abspath(os.path.join(project_name, '.git'))]

            if len(files_to_add_in_backup_zip) > 0:
                os.makedirs(os.path.relpath('backups'), exist_ok=True)
                fd, backup_zip = tempfile.mkstemp(suffix='.zip', prefix=f'backup-{project_name}-', \
                    dir=os.path.relpath('backups'))
                backup_zip_file = os.fdopen(fd, 'wb')
                with ZipFile(backup_zip_file, 'w') as zip:
                    for file_to_add_in_backup_zip in files_to_add_in_backup_zip:
                        zip.write(file_to_add_in_backup_zip)
                pinfo(f'Backup stored at "{backup_zip}"')
            else:
                pinfo('No files or folders to backup')
                backup_zip = "<Empty/>"
            error_occured = False
        except Exception as e:
            pwarn(f"{type(e).__name__} occurred -> {e}")
            perror(f'Could not take safety backup')
            error_occured = True
        finally:
            os.chdir(actual_cwd)
        return backup_zip, error_occured
    
    @staticmethod
    def restore_safe_backup(root, working_dir, backup_zip):
        if os.path.isfile('' if backup_zip is None else backup_zip):
            actual_cwd = os.getcwd()
            try:
                with ZipFile(backup_zip, 'r') as zip:
                    testzip_ret = zip.testzip()
                    if testzip_ret is not None:
                        raise BadZipFile(
                            f'Bad file found {testzip_ret} in {zip.filename}'
                        )
                    if os.path.isdir('' if root is None else root):
                        for _file_or_dir in [_dir for _dir in \
                            os.listdir(root) if _dir != '.git']:
                            try:
                                shutil.rmtree(os.path.relpath(
                                    os.path.join(root, _file_or_dir)))
                            except NotADirectoryError:
                                os.unlink(os.path.relpath(
                                    os.path.join(root, _file_or_dir)))
                            except PermissionError as e:
                                pwarn(f"{type(e).__name__} occurred -> {e}")
                    os.chdir(working_dir)
                    pinfo(f'Backing up from "{zip.filename}"')            
                    zip.printdir()
                    zip.extractall()
            except (BadZipFile, PermissionError) as e:
                perror(f"{type(e).__name__} occured -> {e}")
                pwarn('Could not take the safety backup')
            finally:
                os.chdir(actual_cwd)
        else:
            pwarn('Could not find any backup to restore!')

    @staticmethod
    def delete_backup_zip(backup_zip, delete_backup):
        if delete_backup is None and \
            os.path.isfile('' if backup_zip is None \
                else backup_zip):
            should_delete_backup = ask('Do you want to delete the backup zip?', \
                choices=['yes', 'no'], default='no', on_error=lambda *argv: True)
            delete_backup = should_delete_backup == 'yes'
        else:
            delete_backup = False
        if delete_backup:
            pinfo(f'Deleting safety backup "{backup_zip}"')
            try:
                os.unlink(backup_zip)
            except (FileNotFoundError, PermissionError) as e:
                perror(f'{type(e).__name__} occurred -> {e}')
                pwarn(f'Could not delete safety backup "{backup_zip}"')
                return False
            return True
        return None
    
    @staticmethod
    def post_build_activity(fn):
        @wraps(fn)
        def inner(*argv):
            build_data = fn(*argv)
            if not build_data.status:
                InternalActions.restore_safe_backup(
                    build_data.root, build_data.cwd, build_data.backup_zip
                )
            if InternalActions.delete_backup_zip(
                build_data.backup_zip, build_data.delete_backup):
                pinfo('Backup file has been removed successfully.')
            return build_data.status
        return inner
