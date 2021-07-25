# Any-Project

Any-Project is a python module, helps to build any basic skeleton file structure of "any project".

## Version

The current version of this module is `0.1.0b0`. It is still in BETA stage and supported in `python 3.6+`.

You can check the program's version using the below command.

```bash
any-project -v
```

## Installation

I have not released this module in [PyPi](https://pypi.org/user/antaripchatterjee/) yet, but you can download it from GitHub and install it locally using `setup.py`.

### Using git

```bash
git clone https://github.com/antaripchatterjee/Any-Project.git
cd Any-Project
python setup.py install
```

Run the below command after installation is finised, if you wish to clear the generated folders i.e. `Any_Project.egg-info`, `build`, and `dist`.

```bash
python clear.py
```

## Uninstallation

Simply use `pip` tool to uninstall, whenever you feel that this module is no longer required.

```bash
pip uninstall any_project
```

## Usage

You can use the module from CLI, although you can also use it's API in your own python code.

### Initializing a project-structure

```bash
any-project -init project_dir:TestProject
```

The above command will initialize a new project. First it will create a new folder `project_dir` inside current working directory and then `TestProject` will be initialized with a `project-structure.yaml` document.

### Building the project-structure

Simply type below command to build the newly created project structure.

```bash
any-project -build test_project
```

It will build the `default` action from the `project-structure.yaml` of `TestProject`.

> Later I will provide more detail on it's usages and how you can have your custom action.

> Also I will bring the documentation on it's API level usages with the first stable release of this module.

## License

This module has been licensed under [MIT License](https://github.com/antaripchatterjee/Any-Project/blob/master/LICENSE).
