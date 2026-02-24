from configparser import ConfigParser
 
 
def read_param(filename, section):
    # create a parser
    parser = ConfigParser()
    # read config file
    parser.read(filename)
 
    # get section, default to postgresql
    outval = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            outval[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))
 
    return outval
    
    
def section_exists_and_has_fields(filename, section, required_fields):
   # Check whether a section exists in the file and contains all required fields valorized.

    parser = ConfigParser()
    parser.read(filename)

    if not parser.has_section(section):
        return False

    for field in required_fields:
        if not parser.has_option(section, field) or parser.get(section, field).strip() == '':
            return False

    return True