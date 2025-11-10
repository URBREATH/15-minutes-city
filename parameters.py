import configparser
import ast

def read_param(file_path, section):
    config = configparser.ConfigParser()
    config.optionxform = str  # preserva maiuscole/minuscole
    config.read(file_path)
    params = {}
    if section in config:
        for key in config[section]:
            value = config[section][key]
            if value.strip() == '':
                params[key] = None
                continue
            try:
                value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                value = value
            params[key] = value
    return params
