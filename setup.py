from setuptools import setup
from any_project import __program__
from any_project import __version__


def readme():
    with open('./README.md') as readme_fp:
        README = readme_fp.read()
    return README


setup(
    name=__program__,
    version=__version__,
    description='''
        {0} is a python module, helps to build a basic skeleton file structure of any project.
        Current version of this module is {1}
    '''.format(__program__, __version__),
    long_description=readme(),
    long_description_content_type='text/markdown',
    url="https://github.com/antaripchatterjee/Any-Project",
    author="Antarip Chatterjee",
    author_email="antarip.chatterjee22@gmail.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: Unix",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.6",
        "Environment :: Console",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Topic :: Education",
        "Topic :: Software Development"
    ],
    packages=["any_project"],
    install_requires=[
        'gitdb==4.0.7',
        'GitPython==3.1.14',
        'oyaml==1.0',
        'PyMsgPrompt==1.3.0',
        'PyYAML==5.4.1',
        'Send2Trash==1.5.0',
        'smmap==4.0.0'
    ],
    include_package_data=True,
    entry_points={
        "console_scripts" : [
            "any-project=any_project.cli:main"
        ]
    }
)