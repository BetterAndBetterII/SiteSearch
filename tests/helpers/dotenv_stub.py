import sys, types

dotenv_mod = types.ModuleType('dotenv')

def load_dotenv(*args, **kwargs):
    return None

dotenv_mod.load_dotenv = load_dotenv

sys.modules['dotenv'] = dotenv_mod
