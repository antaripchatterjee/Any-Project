from any_project import __module__
from collections import OrderedDict
from pymsgprompt.logger import pinfo, perror, pwarn
import os, re, ast, git, glob, tempfile, shutil
from zipfile import ZipFile

class InternalActions(object):
    @staticmethod
    def add_git_commit(root, msg):
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
    def get_overwriting_content(filename, new_content):
        existing_file_lines = open(filename).read().split('\n')
        new_lines_to_write = new_content.split('\n')
        pattern = r'^(?:[\s]*([-+]\d+)[\s]*[\:][\s]?)?(.*)$'
        actual_index = 0
        for temp in new_lines_to_write:
            if temp.rstrip() != '':
                actual_index += 1
                m = re.match(pattern, temp)
                line, data = m.groups()
                if line is None:
                    if actual_index == 1: return new_content
                    line = '0'
                line = int(line)
                if data is None:
                    data = ''

                if abs(line) > len(existing_file_lines):
                    line = 0

                if line == 0:
                    existing_file_lines.append(data)
                elif line < 0:
                    if data.strip() == '':
                        existing_file_lines.pop(abs(line) - 1)
                    else:
                        existing_file_lines[abs(line)-1] = data
                elif line > 0:
                    existing_file_lines.insert(abs(line)-1, data)
        return '\n'.join(existing_file_lines)

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

            if isinstance(val, str):
                new_file = os.path.relpath(os.path.join(root, key))
                if setup_obj is None:
                    write_file = True
                else:
                    write_file = setup_obj.on_create_file(new_file)
                if write_file:
                    if os.path.isfile(new_file):
                        pinfo(f'Overwriting file : {new_file}')
                        is_new_file = False
                    else:
                        pinfo(f'Creating file  : {new_file}')
                        is_new_file = True
                    try:
                        content_to_write = os.path.expandvars(val).format(
                            prompts = setup_obj.prompts if setup_obj \
                                is not None else None,
                            consts = constants
                        )
                        if not is_new_file:
                            content_to_write = InternalActions.get_overwriting_content( \
                                new_file, content_to_write)
                        with open(new_file, 'w') as f:
                            f.write(content_to_write)
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
                        write_directory = setup_obj.on_create_folder(new_folder)
                    if write_directory:
                        if not os.path.isdir(new_folder):
                            pinfo(f'Creating folder: {new_folder}')
                        try:
                            os.makedirs(new_folder, exist_ok=True)
                            if not InternalActions.expand_file_structure(new_folder, val, setup_obj, constants):
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
                            if not InternalActions.expand_file_structure(new_folder, final_inner_value, setup_obj, constants):
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
    def take_safe_backup(working_dir, project_name):
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
        except Exception as e:
            perror(f"{type(e).__name__} occurred -> {e}")
            backup_zip = None
        finally:
            os.chdir(actual_cwd)
        return backup_zip
    
    @staticmethod
    def restore_safe_backup(root, working_dir, backup_zip):
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
                pwarn('Could not find any backup to restore!')
        else:
            pwarn('Could not find any backup to restore!')
