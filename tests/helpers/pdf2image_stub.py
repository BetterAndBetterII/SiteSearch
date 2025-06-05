import sys, types

pdf2image_mod = types.ModuleType('pdf2image')

def convert_from_path(path):
    return []

pdf2image_mod.convert_from_path = convert_from_path
sys.modules['pdf2image'] = pdf2image_mod
