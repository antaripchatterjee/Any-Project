from .application import Actions
from dotenv import load_dotenv
import os

def main():
    dotenv_path = os.path.relpath(
        os.path.join(os.getcwd(), '.env')
    )
    if os.path.isfile(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
    Actions.main()