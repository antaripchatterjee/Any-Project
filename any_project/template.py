from os import getenv
from sys import platform
from datetime import datetime
from getpass import getuser
from collections import OrderedDict
import time


def default_yaml_template(project_name, working_dir):
    is_dst = time.daylight and time.localtime().tm_isdst > 0
    utc_offset = time.altzone if is_dst else time.timezone
    return OrderedDict(
        [
            ('project-name', project_name),
            ('working-dir', working_dir),
            ('constants', OrderedDict([    
                ('version', '0.0.1'),
                ('license', getenv('PROJECT_LICENSE')),
                ('creation_utctime', datetime.utcnow().strftime(r'%d-%b-%Y %H:%M:%S UTC+0:00')),
                ('creation_localtime', datetime.now().strftime(r'%d-%b-%Y %H:%M:%S T{S}{HH}:{MM}'.format(
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

def yaml_template(project_name, working_dir, template_generator):
    return default_yaml_template(project_name, working_dir) \
        if template_generator is None else \
            template_generator(default_yaml_template(project_name, working_dir))