import sys, types

tenacity_mod = types.ModuleType('tenacity')

def retry(*dargs, **dkwargs):
    def wrapper(fn):
        return fn
    return wrapper

def stop_after_attempt(*args, **kwargs):
    return None

def wait_exponential(*args, **kwargs):
    return None

tenacity_mod.retry = retry
tenacity_mod.stop_after_attempt = stop_after_attempt
tenacity_mod.wait_exponential = wait_exponential

sys.modules['tenacity'] = tenacity_mod
