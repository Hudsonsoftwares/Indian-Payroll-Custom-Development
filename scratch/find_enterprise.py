import glob, os

for drive in ['C:', 'D:', 'E:']:
    for p in glob.glob(f'{drive}/**/pos_preparation_display', recursive=True):
        print("Found:", p)
