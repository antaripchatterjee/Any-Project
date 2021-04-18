# YAML_TEMPLATE = '''
# project-name: {project_name}
# project-version: 0.0.1
# project-license: null
# project-creation-time: {project_creation_time}
# project-author: {current_user}
# author-email-id: ${{AUTHOR_EMAIL_ID}}
# working-dir: {YAML_CODE_DIR}
# git-repo: no
# system-platform: {system_platform}
# environment:
# pre-commands:
#     - common:
#         - "echo Creating project template [{project_name}]"
#         - "echo Author: {current_user}"
#         - "echo Timestamp: {project_creation_time}"
# project-structure:

# '''

from os import getenv
from sys import platform
from datetime import datetime
from getpass import getuser
from collections import OrderedDict
import time


def yaml_template(project_name, working_dir):
    is_dst = time.daylight and time.localtime().tm_isdst > 0
    utc_offset = time.altzone if is_dst else time.timezone
    return OrderedDict(
        [
            ('project-name', project_name),
            ('working-dir', working_dir),
            ('constants', OrderedDict([    
                ('version', '0.0.1'),
                ('license', getenv('PROJECT_LICENSE')),
                ('creation_time_utc', datetime.utcnow().strftime(r'%d-%b-%Y %H:%M:%S UTC+0:00')),
                ('creation_time_local', datetime.now().strftime(r'%d-%b-%Y %H:%M:%S T{S}{HH}:{MM}'.format(
                    S='+' if utc_offset <= 0 else '-',
                    HH=int(abs(utc_offset)/3600),
                    MM=int((abs(utc_offset)%3600)/60)
                ))),
                ('author', getuser()),
                ('email_id', getenv('PROJECT_AUTHOR_EMAIL')),
                ('git_repo', False),
                ('platform', platform.lower())
            ])),
            ('environment', OrderedDict([
                ('PROJECT_NAME', project_name)
            ])),
            ('boilerplates', OrderedDict([
                ('default', OrderedDict([
                    ('setup', 'from any_project import DefaultSetup'),
                    ('structure', None)
                ]))
            ]))
        ]
    )