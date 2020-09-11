#!/usr/bin/env python
#-*- coding: utf-8 -*-

import sys
import argparse
import os
import errno
import platform
import odoolib
import io
import socket
from odoo_csv_tools.lib import conf_lib

module_version = '1.4.2'
offline = False
dbname = ''
hostname = ''

##############################################################################
# FUNCTIONS FOR DIRECTORY STRUCTURE
##############################################################################

def create_folder(path):
    """
    Create a folder only if it doesn't exist or if the flag "force" is set.
    """
    if os.path.exists(path) and not force:
        if verbose: sys.stdout.write('Folder %s already exists.\n' % path)
        return

    if verbose: sys.stdout.write('Create folder %s\n' % path)
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

def check_file_exists(func):
    """
    Decorator avoiding to overwrite a file if it already exists
    but still allowing it if the flag "force" is set.
    """
    def wrapper(*args, **kwargs):
        file = args[0]
        if os.path.isfile(file) and not force:
            if verbose: sys.stdout.write('File %s already exists.\n' % file)
            return
        if verbose: sys.stdout.write('Create file %s\n' % file)
        func(*args, **kwargs)
    return wrapper


def is_remote_host(hostname):
    """
    Return True if 'hostname' is not the local host.
    """
    my_host_name = socket.gethostname() 
    my_host_ip = socket.gethostbyname(my_host_name)
    if any(hostname in x for x in [my_host_name, my_host_ip, socket.getfqdn(), 'localhost', '127.0.0.1']):
        return False
    return True
    

@check_file_exists
def create_connection_file_local(file):
    """
    Enforce encrypted connection on remote hosts. 
    Leave unencrypted for local databases.
    """
    is_remote = is_remote_host(host)
    protocol = 'jsonrpcs' if is_remote else 'jsonrpc'
    port = '443' if is_remote else '8069'
    with open(file, 'w') as f:
        f.write("[Connection]\n")
        f.write("hostname = %s\n" % host)
        f.write("database = %s\n" % dbname)
        f.write("login = admin\n")
        f.write("password = admin\n")
        f.write("protocol = %s\n" % protocol)
        f.write("port = %s\n" % port)
        f.write("uid = %s\n" % userid)


@check_file_exists
def create_connection_file_remote(file, hostname):
    """
    Just a preset for encrypted connection.
    """
    with open(file, 'w') as f:
        f.write("[Connection]\n")
        f.write("hostname = %s\n" % hostname)
        f.write("database = \n")
        f.write("login = \n")
        f.write("password = \n")
        f.write("protocol = jsonrpcs\n")
        f.write("port = 443\n")
        f.write("uid = %s\n" % userid)


@check_file_exists
def create_cleanup_script(file):
    """
    Create the shell script to empty the folder "data".
    """
    if platform.system() == 'Windows':
        with open(file, 'w') as f:
            f.write("@echo off\n\n")
            f.write("set DIR=%s\n" % data_dir_name)
            f.write("del /F /S /Q %DIR%\*\n")
    else:
        with open(file, 'w') as f:
            f.write("#!/usr/bin/env bash\n\n")
            f.write("DIR=%s%s\n" % (data_dir_name, os.sep))
            f.write("rm -rf --interactive=never $DIR\n")
            f.write("mkdir -p $DIR\n")
        os.chmod(file, 0o755)


@check_file_exists
def create_transform_script(file):
    """
    Create the shell script skeleton that launches all transform commands.
    """
    if platform.system() == 'Windows':
        with open(file, 'w') as f:
            f.write("@echo off\n\n")
            f.write("set LOGDIR=%s\n" % log_dir_name)
            f.write("set DATADIR=%s\n\n" % data_dir_name)
            f.write("call cleanup_data_dir.cmd\n\n")
            f.write("REM Add here all transform commands\n")
            f.write("REM python my_model.py > %LOGDIR%\\transform_$1_out.log 2> %LOGDIR%\\transform_$1_err.log\n")
    else:
        with open(file, 'w') as f:
            f.write("#!/usr/bin/env bash\n\n")
            f.write("LOGDIR=%s\n" % log_dir_name)
            f.write("DATADIR=%s\n\n" % data_dir_name)
            f.write("COLOR='\\033[1;32m'\n")
            f.write("NC='\\033[0m'\n\n")
            f.write("msg() {\n")
            f.write("    start=$(date +%s.%3N)\n")
            f.write("    PID=$!\n")
            f.write("    printf \"($PID) Transform ${COLOR}$1${NC} [\"\n")
            f.write("    while kill -0 $PID 2> /dev/null; do\n")
            f.write("        printf  \"▓\"\n")
            f.write("        sleep 1\n")
            f.write("    done\n")
            f.write("    end=$(date +%s.%3N)\n")
            f.write("    runtime=$(python -c \"print '%u:%02u' % ((${end} - ${start})/60, (${end} - ${start})%60)\")\n")
            f.write("    printf \"] $runtime \\n\"\n")
            f.write("}\n\n")
            f.write("load_script() {\n")
            f.write("    #rm -f $DATADIR/*$1*.csv*\n")
            f.write("    rm -f $LOGDIR/transform_$1_*.log\n")
            f.write("    python $1.py > $LOGDIR/transform_$1_out.log 2> $LOGDIR/transform_$1_err.log &\n")
            f.write("    msg \"$1\"\n")
            f.write("}\n\n")
            f.write("./cleanup_data_dir.sh\n\n")
            f.write("# Add here all transform commands\n")
            f.write("# load_script python_script (without extension)\n")
            f.write("chmod +x *.sh\n")
        os.chmod(file, 0o755)
    

@check_file_exists
def create_load_script(file):
    """
    Create the shell script skeleton that launches all load commands.
    """
    if platform.system() == 'Windows':
        with open(file, 'w') as f:
            f.write("@echo off\n\n")
            f.write("set LOGDIR=%s\n\n" % log_dir_name)
            f.write("REM Add here all load commands\n")
            f.write("REM my_model.cmd > %LOGDIR%\\load_$1_out.log 2> %LOGDIR%\\load_$1_err.log\n")
    else:
        with open(file, 'w') as f:
            f.write("#!/usr/bin/env bash\n\n")
            f.write("LOGDIR=%s\n\n" % log_dir_name)
            f.write("COLOR='\\033[1;32m'\n")
            f.write("NC='\\033[0m'\n\n")
            f.write("user_interrupt() {\n")
            f.write("    echo -e \"\\n\\nKeyboard Interrupt detected.\"\n")
            f.write("    echo -e \"\\nKill import tasks...\"\n")
            f.write("    # Kill the current import\n")
            f.write("    killall odoo-import-thread.py\n")
            f.write("    sleep 2\n")
            f.write("    # Kill the next launched import (--fail)\n")
            f.write("    killall odoo-import-thread.py\n")
            f.write("    exit\n")
            f.write("}\n\n")
            f.write("msg() {\n")
            f.write("    start=$(date +%s.%3N)\n")
            f.write("    PID=$!\n")
            f.write("    printf \"($PID) Load ${COLOR}$1${NC} [\"\n")
            f.write("    while kill -0 $PID 2> /dev/null; do\n")
            f.write("        printf  \"▓\"\n")
            f.write("        sleep 1\n")
            f.write("    done\n")
            f.write("    end=$(date +%s.%3N)\n")
            f.write("    runtime=$(python -c \"print '%u:%02u' % ((${end} - ${start})/60, (${end} - ${start})%60)\")\n")
            f.write("    printf \"] $runtime \\n\"\n")
            f.write("}\n\n")
            f.write("load_script() {\n")
            f.write("    # rm -f \$LOGDIR/load_$1_*.log\n")
            f.write("    ./$1.sh > $LOGDIR/load_$1_out.log 2> $LOGDIR/load_$1_err.log &\n")
            f.write("    msg \"$1\"\n")
            f.write("}\n\n")
            f.write("trap user_interrupt SIGINT\n")
            f.write("trap user_interrupt SIGTSTP\n\n")
            f.write("# Add here all load commands\n")
            f.write("# load_script shell_script (without extension)\n")
        os.chmod(file, 0o755)


@check_file_exists
def create_file_prefix(file):
    """
    Create the skeleton of prefix.py.
    """
    with open(file, 'w') as f:
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write("# This file defines xml_id prefixes and projectwise variables.\n\n")
        f.write("# Defines here a identifier used in the created XML_ID.\n")
        f.write("project_name = '%s'\n" % project_name)
        f.write("\n")
        f.write("# CONSTANTS\n")
        f.write("COMPANY_ID = 'base.main_company'\n")
        f.write("\n")
        f.write("# Define here all values in client files considered as TRUE value.\n")
        f.write("true_values = ['TRUE', 'True', 'true', 'YES', 'Yes', 'yes', 'Y', 'y', '1', '1,0', '1.0']\n")
        f.write("# Define here all values in client files considered as FALSE value.\n")
        f.write("false_values = ['FALSE', 'False', 'false', 'NO', 'No', 'no', 'N', 'n', '0', '0,0', '0.0']\n")
        f.write("\n")
        f.write("# Define the languages used in the import.\n")
        f.write("# These will be installed by calling install_lang.py\n")
        f.write("# Key: language code used in the client file\n")
        f.write("# Value: the Odoo lang code\n")
        f.write("res_lang_map = {\n")
        f.write("#    'E': 'en_US',\n")
        f.write("}\n\n")
        f.write("# XML ID PREFIXES\n")
    

@check_file_exists
def create_file_mapping(file):
    """
    Create the skeleton of mapping.py.
    """
    with open(file, 'w') as f:
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write("# This file defines mapping dictionaries.\n\n")
        f.write("# MAPPING DICTIONARIES\n")
        f.write("# Use odoo_import_scaffold with option --map-selection to\n")
        f.write("# automatically build dictionaries of selection fields.\n\n")


@check_file_exists
def create_file_files(file):
    """
    Create the skeleton of files.py.
    """
    with open(file, 'w') as f:
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write("# This file defines the names of all used files.\n\n")
        f.write("import os\n")
        f.write("\n")
        f.write("# Folders\n")
        f.write("conf_dir = '%s'\n" % conf_dir_name)
        f.write("data_src_dir = '%s'\n" % orig_dir_name)
        f.write("data_raw_dir = '%s%sbinary%s' % (data_src_dir,os.sep, os.sep)\n")
        f.write("data_dest_dir = '%s'\n" % data_dir_name)
        f.write("\n")
        f.write("# Configuration\n")
        f.write("config_file = os.path.join(conf_dir,'connection.conf')\n")
        f.write("\n")
        f.write("# Declare here all data files\n")

        if not model:
            f.write("# Client file: src_my_model = os.path.join(data_src_dir, 'my_model.csv')\n")
            f.write("# Import file: dest_my_model = os.path.join(data_dest_dir, 'my.model.csv')\n")
        
        f.write("\n")


@check_file_exists
def create_file_lib(file):
    """
    Create the skeleton of funclib.py.
    """
    with open(file, 'w') as f:
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write("# This file defines common functions.\n\n")
        f.write("from odoo_csv_tools.lib import mapper\n")
        f.write("from odoo_csv_tools.lib.transform import Processor\n")
        f.write("from prefix import *\n")
        f.write("from mapping import *\n")
        f.write("from datetime import datetime\n")
        f.write("\n\n")
        f.write("nvl = lambda a, b: a or b\n")
        f.write("\n\n")
        f.write("def keep_numbers(val):\n")
        f.write("    return filter(lambda x: x.isdigit(), val)\n")
        f.write("\n\n")
        f.write("def keep_letters(val):\n")
        f.write("    return filter(lambda x: x.isalpha(), val)\n")
        f.write("\n\n")
        f.write("def remove_accents(val):\n")
        f.write("    replacements = [\n")
        f.write("                   (u'\%s', 'a'),\n" % 'xe0')
        f.write("                   (u'\%s', 'a'),\n" % 'xe1')
        f.write("                   (u'\%s', 'a'),\n" % 'xe2')
        f.write("                   (u'\%s', 'a'),\n" % 'xe3')
        f.write("                   (u'\%s', 'a'),\n" % 'xe4')
        f.write("                   (u'\%s', 'a'),\n" % 'xe5')
        f.write("                   (u'\%s', 'A'),\n" % 'xc0')
        f.write("                   (u'\%s', 'A'),\n" % 'xc1')
        f.write("                   (u'\%s', 'A'),\n" % 'xc2')
        f.write("                   (u'\%s', 'A'),\n" % 'xc3')
        f.write("                   (u'\%s', 'A'),\n" % 'xc4')
        f.write("                   (u'\%s', 'A'),\n" % 'xc5')
        f.write("                   (u'\%s', 'e'),\n" % 'xe8')
        f.write("                   (u'\%s', 'e'),\n" % 'xe9')
        f.write("                   (u'\%s', 'e'),\n" % 'xea')
        f.write("                   (u'\%s', 'e'),\n" % 'xeb')
        f.write("                   (u'\%s', 'E'),\n" % 'xc8')
        f.write("                   (u'\%s', 'E'),\n" % 'xc9')
        f.write("                   (u'\%s', 'E'),\n" % 'xca')
        f.write("                   (u'\%s', 'E'),\n" % 'xcb')
        f.write("                   (u'\%s', 'i'),\n" % 'xec')
        f.write("                   (u'\%s', 'i'),\n" % 'xed')
        f.write("                   (u'\%s', 'i'),\n" % 'xee')
        f.write("                   (u'\%s', 'i'),\n" % 'xef')
        f.write("                   (u'\%s', 'I'),\n" % 'xcc')
        f.write("                   (u'\%s', 'I'),\n" % 'xcd')
        f.write("                   (u'\%s', 'I'),\n" % 'xce')
        f.write("                   (u'\%s', 'I'),\n" % 'xcf')
        f.write("                   (u'\%s', 'o'),\n" % 'xf2')
        f.write("                   (u'\%s', 'o'),\n" % 'xf3')
        f.write("                   (u'\%s', 'o'),\n" % 'xf4')
        f.write("                   (u'\%s', 'o'),\n" % 'xf5')
        f.write("                   (u'\%s', 'o'),\n" % 'xf6')
        f.write("                   (u'\%s', 'O'),\n" % 'xd2')
        f.write("                   (u'\%s', 'O'),\n" % 'xd3')
        f.write("                   (u'\%s', 'O'),\n" % 'xd4')
        f.write("                   (u'\%s', 'O'),\n" % 'xd5')
        f.write("                   (u'\%s', 'O'),\n" % 'xd6')
        f.write("                   (u'\%s', 'c'),\n" % 'xe7')
        f.write("                   ]\n")
        f.write("    for a, b in replacements:\n")
        f.write("        val = val.replace(a, b)\n")
        f.write("    return val\n")
        f.write("\n\n")
        f.write("def keep_column_value(val, column):\n")
        f.write("    def keep_column_value_fun(line):\n")
        f.write("        if line[column] != val:\n")
        f.write("            raise SkippingException(\"Column %s with wrong value %s\" % (column, val))\n")
        f.write("        return line[column]\n")
        f.write("    return keep_column_value_fun\n")
        f.write("\n")


@check_file_exists
def create_file_clean_data(file):
    """
    Create the skeleton of clean_data.py.
    """
    with open(file, 'w') as f:
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write("# This script remove the data created by the import.\n\n")
        f.write("import odoolib\n")
        f.write("from odoo_csv_tools.lib import conf_lib\n")
        f.write("from prefix import *\n")
        f.write("from files import *\n\n")
        f.write("connection = conf_lib.get_server_connection(config_file)\n\n")
        f.write("def delete_model_data(connection, model, demo = False):\n")
        f.write("    model_model = connection.get_model(model)\n")
        f.write("    record_ids = model_model.search([])\n")
        f.write("    if demo:\n")
        f.write("        print 'Will remove %s records from %s' % (len(record_ids), model)\n")
        f.write("    else:\n")
        f.write("        print 'Remove %s records from %s' % (len(record_ids), model)\n")
        f.write("        model_model.unlink(record_ids)\n")
        f.write("\n\n")
        f.write("def delete_xml_id(connection, model, module, demo = False):\n")
        f.write("    data_model = connection.get_model('ir.model.data')\n")
        f.write("    data_ids = data_model.search([('module', '=', module), ('model', '=', model)])\n")
        f.write("    records = data_model.read(data_ids, ['res_id'])\n")
        f.write("    record_ids = []\n")
        f.write("    for rec in records:\n")
        f.write("        record_ids.append(rec['res_id'])\n")
        f.write("    if demo:\n")
        f.write("        print 'Will remove %s xml_id %s from %s' % (len(record_ids), module, model)\n")
        f.write("    else:\n")
        f.write("        print 'Remove %s xml_id %s from %s' % (len(record_ids), module, model)\n")
        f.write("        connection.get_model(model).unlink(record_ids)\n")
        f.write("\n\n")
        f.write("demo = True\n\n")


@check_file_exists
def create_file_install_lang(file):
    """
    Create the skeleton of install_lang.py.
    """
    with open(file, 'w') as f:
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write("import odoolib\n")
        f.write("from prefix import *\n")
        f.write("from files import *\n")
        f.write("from odoo_csv_tools.lib import conf_lib\n\n")
        f.write("connection = conf_lib.get_server_connection(config_file)\n\n")
        f.write("model_lang = connection.get_model('base.language.install')\n\n")
        f.write("for key in res_lang_map.keys():\n")
        f.write("    lang = res_lang_map[key]\n")
        f.write("    res = model_lang.create({'lang': lang})\n")
        f.write("    model_lang.lang_install(res)\n")


@check_file_exists
def create_file_install_modules(file):
    """
    Create the skeleton of install_modules.py.
    """
    with open(file, 'w') as f:
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write("import sys\n")
        f.write("import odoolib\n")
        f.write("from prefix import *\n")
        f.write("from files import *\n")
        f.write("from odoo_csv_tools.lib import conf_lib\n")
        f.write("from odoo_csv_tools.lib.internal.rpc_thread import RpcThread\n")
        f.write("from files import config_file\n\n")
        f.write("connection = conf_lib.get_server_connection(config_file)\n\n")
        f.write("model_module = connection.get_model('ir.module.module')\n")
        f.write("model_module.update_list()\n\n")
        f.write("# Set the modules to install\n")
        f.write("module_names = []\n\n")
        f.write("module_ids = model_module.search_read([['name', 'in', module_names]])\n\n")
        f.write("rpc_thread = RpcThread(1)\n\n")
        f.write("for module in module_ids:\n")
        f.write("    if module['state'] == 'installed':\n")
        f.write("        rpc_thread.spawn_thread(model_module.button_immediate_upgrade, [module['id']])\n")
        f.write("    else:\n")
        f.write("        rpc_thread.spawn_thread(model_module.button_immediate_install, [module['id']])\n")


@check_file_exists
def create_file_uninstall_modules(file):
    """
    Create the skeleton of uninstall_modules.py.
    """
    with open(file, 'w') as f:
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write("import sys\n")
        f.write("import odoolib\n")
        f.write("from prefix import *\n")
        f.write("from files import *\n")
        f.write("from odoo_csv_tools.lib import conf_lib\n")
        f.write("from odoo_csv_tools.lib.internal.rpc_thread import RpcThread\n")
        f.write("from files import config_file\n\n")
        f.write("connection = conf_lib.get_server_connection(config_file)\n\n")
        f.write("model_module = connection.get_model('ir.module.module')\n")
        f.write("model_module.update_list()\n\n")
        f.write("# Set the modules to uninstall\n")
        f.write("module_names = []\n\n")
        f.write("module_ids = model_module.search_read([['name', 'in', module_names]])\n\n")
        f.write("rpc_thread = RpcThread(1)\n\n")
        f.write("for module in module_ids:\n")
        f.write("    if module['state'] == 'installed':\n")
        f.write("        rpc_thread.spawn_thread(model_module.button_immediate_uninstall, [module['id']])\n")


@check_file_exists
def create_file_init_map(file):
    """
    Create the skeleton of init_map.py.
    """
    with open(file, 'w') as f:
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write("import odoolib\n")
        f.write("from prefix import *\n")
        f.write("from files import *\n")
        f.write("from odoo_csv_tools.lib import conf_lib\n")
        f.write("import json\n")
        f.write("import io\n\n")
        f.write("connection = conf_lib.get_server_connection(config_file)\n\n")
        f.write("def build_map_product_category_id(filename=''):\n")
        f.write("    # Build a dictionary {product_category : xml_id} of all existing product_category.\n")
        f.write("    model_data = connection.get_model('ir.model.data')\n")
        f.write("    model_product_category = connection.get_model('product.category')\n")
        f.write("    recs = model_product_category.search_read([], ['id', 'name'])\n\n")
        f.write("    res_map = {}\n")
        f.write("    for rec in recs:\n")
        f.write("        data = model_data.search_read([('res_id', '=', rec['id']), ('model', '=', 'product.category')], ['module', 'name'])\n")
        f.write("        if len(data):\n")
        f.write("            key = rec['name'].strip()\n")
        f.write("            val = '.'.join([data[0]['module'], data[0]['name'] ])\n")
        f.write("            res_map[key] = val.strip()\n")
        f.write("        # else:\n")
        f.write("        #     print 'Product category %s has no XML_ID (id: %s)' % (rec['name'], rec['id'])\n\n")
        f.write("    if filename:\n")
        f.write("        with open(filename, 'w') as fp:\n")
        f.write("            json.dump(res_map, fp)\n\n")
        f.write("    return res_map\n\n")
        f.write("# Execute mapping\n")
        f.write("# dummy = build_map_product_category_id(work_map_product_category_id)\n\n")
        f.write("# Add in files.py\n")
        f.write("# work_map_product_category_id = os.path.join(data_src_dir, 'work_map_product_category_id.json')\n\n")
        f.write("# Add in transformation script\n")
        f.write("# map_product_category_id = {}\n")
        f.write("# with io.open(work_map_product_category_id, 'r') as fp:\n")
        f.write("#     map_product_category_id = json.load(fp, encoding='utf-8')\n\n")
        f.write("# Add in transformation script to map 'id' column. REVIEW COLUNM NAME and PREFIX\n")
        f.write("# def handle_product_category_id(line):\n")
        f.write("#     categ_name = line['Product Category']\n")
        f.write("#     try:\n")
        f.write("#         categ_xml_id = map_product_category_id[categ_name]\n")
        f.write("#     except:\n")
        f.write("#         categ_xml_id = mapper.m2o(PREFIX_PRODUCT_CATEGORY, 'Product Category')(line)\n")
        f.write("#     return categ_xml_id\n\n")
        f.write("##################################################################################################\n\n")
        f.write("def build_account_map(company_id, filename=''):\n")
        f.write("    # Build a dictionary {account_code : xml_id} of all existing accounts of a company.\n")
        f.write("    model_data = connection.get_model('ir.model.data')\n")
        f.write("    model_account = connection.get_model('account.account')\n")
        f.write("    recs = model_account.search_read([('company_id', '=', company_id)], ['id', 'code'])\n\n")
        f.write("    res_map = {}\n")
        f.write("    for rec in recs:\n")
        f.write("        data = model_data.search_read([('res_id', '=', rec['id']), ('model', '=', 'account.account')], ['module', 'name'])\n")
        f.write("        if len(data):\n")
        f.write("            key = rec['code'].strip()\n")
        f.write("            val = '.'.join([data[0]['module'], data[0]['name'] ])\n")
        f.write("            res_map[key] = val.strip()\n")
        f.write("        # else:\n")
        f.write("        #     print 'Account %s has no XML_ID' % rec['code']\n\n")
        f.write("    if filename:\n")
        f.write("        with open(filename, 'w') as fp:\n")
        f.write("            json.dump(res_map, fp)\n\n")
        f.write("    return res_map\n\n")
        f.write("# Execute mapping\n")
        f.write("# dummy = build_account_map(1, work_map_account_code_id)\n\n")
        f.write("# Add in files.py\n")
        f.write("# work_map_account_code_id = os.path.join(data_src_dir, 'work_map_account_code_id.json')\n\n")
        f.write("# Add in transformation script\n")
        f.write("# map_account_code_id = {}\n")
        f.write("# with io.open(work_map_account_code_id, 'r') as fp:\n")
        f.write("#     map_account_code_id = json.load(fp, encoding='utf-8')\n\n")
        f.write("# Add in transformation script to map 'id' column. REVIEW COLUNM NAME and PREFIX\n")
        f.write("# def handle_account_account_id_map(line):\n")
        f.write("#     code = line['Accounts']\n")
        f.write("#     try:\n")
        f.write("#         val = map_account_code_id[code]\n")
        f.write("#     except:\n")
        f.write("#         val = mapper.m2o(PREFIX_ACCOUNT_ACCOUNT, 'Accounts')(line)\n")
        f.write("#     return val\n\n")
        f.write("##################################################################################################\n\n")


def scaffold_dir():
    """
    Create the whole directory structure and the basic project files.
    """
    create_folder(conf_dir)
    create_folder(orig_dir)
    create_folder(orig_raw_dir)
    create_folder(data_dir)
    create_folder(log_dir)

    create_connection_file_local(os.path.join(conf_dir, 'connection.conf'))
    create_connection_file_local(os.path.join(conf_dir, 'connection.local'))
    create_connection_file_remote(os.path.join(conf_dir, 'connection.staging'), '.dev.odoo.com')
    create_connection_file_remote(os.path.join(conf_dir, 'connection.master'), '.odoo.com')

    create_cleanup_script(os.path.join(base_dir, '%s%s' % ('cleanup_data_dir', script_extension)))
    create_transform_script(os.path.join(base_dir, '%s%s' % ('transform', script_extension)))
    create_load_script(os.path.join(base_dir, '%s%s' % ('load', script_extension)))
    create_file_prefix(os.path.join(base_dir, 'prefix.py'))
    create_file_mapping(os.path.join(base_dir, 'mapping.py'))
    create_file_files(os.path.join(base_dir, 'files.py'))
    create_file_lib(os.path.join(base_dir, 'funclib.py'))
    create_file_clean_data(os.path.join(base_dir, 'clean_data.py'))
    create_file_install_lang(os.path.join(base_dir, 'install_lang.py'))
    create_file_install_modules(os.path.join(base_dir, 'install_modules.py'))
    create_file_uninstall_modules(os.path.join(base_dir, 'uninstall_modules.py'))
    create_file_init_map(os.path.join(base_dir, 'init_map.py'))

    sys.stdout.write("Project created in %s\n" % os.path.abspath(base_dir))

##############################################################################
# FUNCTIONS FOR MODEL SKELETON CODE
##############################################################################

class ModelField:
    """
    - manage how to get a suited mapper function (get_mapper_command)
    - manage how to document itself (get_info)
    """
    def __init__(self, connection, properties):
        self.connection = connection
        self.properties = properties
        self.import_warn_msg = []
        self.id = properties.get('id')
        self.name = properties.get('name')
        self.type = properties.get('ttype')
        self.required = properties.get('required')
        self.readonly = properties.get('readonly')
        self.string = properties.get('field_description')
        self.store = properties.get('store')
        self.track_visibility = properties.get('track_visibility')
        self.related = properties.get('related')
        self.relation = properties.get('relation')
        self.depends = properties.get('depends')
        self.compute = self.__get_compute()
        self.selection = self.__get_selection()
        self.default_value = self.__get_default()

        # Reasons avoiding to import a field -> commented by get_info
        if self.related and self.store:
            self.import_warn_msg.append('related stored')
        if not self.store and not self.related:
            self.import_warn_msg.append('non stored')
        if len(self.compute) > 1:
            self.import_warn_msg.append('computed')


    def __get_selection(self):
        """
        Fetch the selection values of a field.
        Return a list of strings  "'technical_value': 'visible_value'" 
        or an emplty list if no selection exists.
        """
        l = []
        model_model = self.connection.get_model(model)
        try:
            vals = model_model.fields_get([self.name]).get(self.name).get('selection')
            if not vals:
                return l
            for sel in vals:
                l.append("'%s'%s%s" % (sel[0], selection_sep, sel[1]))
        except:
            pass
        return l

    def __get_default(self):
        """
        Fetch the default value of a field.
        Return a list of strings (because the default value can be a multiline value)
        or an emplty list if no default value exists.
        """
        model_model = self.connection.get_model(model)
        val = model_model.default_get([self.name]).get(self.name, '')
        l = []

        try:
            val = str(val)
        except:
            pass

        for line in val.splitlines():
            l.append(line)

        if maxdescr > -1 and len(l) > max(1, maxdescr):
            l = l[:maxdescr] + ['[truncated...]']

        return l

    def __get_compute(self):
        """
        Fetch the compute method of a field.
        Return a list of strings (because the compute method is often a multiline value)
        or an emplty list if no compute method exists.
        """
        val = self.properties.get('compute')
        l = []

        val = str(val)
        for line in val.splitlines():
            l.append(line)

        if maxdescr > -1 and len(l) > maxdescr:
            l = l[:maxdescr] + ['[truncated...]']

        return l

    def get_info(self):
        """
        Build the complete block of text describing a field.
        """
        self.info = "%s (#%s): %s%s%s%s%s," % ( self.string, self.id,
                                    'stored' if self.store else 'non stored',
                                    ', required' if self.required else ', optional',
                                    ', readonly' if self.readonly else '',
                                    ', track_visibility (%s)' % self.track_visibility if self.track_visibility else '',
                                    ', related (=%s)' % self.related if self.related else '',
                                    )

        self.info = "%s %s" % (self.info, self.type)

        if self.relation:
            self.info = "%s -> %s" % (self.info, self.relation)
            # Add XMLID summary in field info
            model_data = self.connection.get_model('ir.model.data')
            external_prefixes = model_data.read_group([('model', '=', self.relation)], ['module'], ['module'])
            if external_prefixes:
                self.info = "%s - with xml_id in module(s):" % self.info
                for data in external_prefixes:
                    self.info = '%s %s(%s)' % (self.info, data['module'], data['module_count'])

        if self.selection:
            self.info = "%s\n    # SELECTION: %s" % (self.info, ', '.join(self.selection))

        if self.default_value:
            if len(self.default_value) == 1:
                self.info = '%s\n    # DEFAULT: %s' % (self.info, self.default_value[0])
            else:
                self.info = '%s\n    # DEFAULT: \n    # %s' % (self.info, '\n    # '.join(self.default_value))

        if len(self.compute) > 1:
            self.info = '%s\n    # COMPUTE: depends on %s\n    # %s' % (self.info, self.depends, '\n    # '.join(self.compute))

        if self.import_warn_msg:
            self.info = "%s\n%s %s" % (self.info, '    # AVOID THIS FIELD:', ', '.join(self.import_warn_msg))
        
        if sys.version_info >= (3, 0, 0):
            return self.info
        else:
            return u''.join((self.info)).encode('utf-8')

    def get_name(self):
        return self.name if fieldname=='tech' else self.string

    def get_mapping_name(self):
        """
        Return the field name as needed in the import file.
        """
        return '/'.join((self.name, 'id')) if self.type in ('many2one', 'many2many') else self.name
    
    def get_mapper_command(self):
        """
        Return a suited mapper function according to the field properties and skeleton options.
        """
        if self.name == 'id':
            if wxmlid:
                return "mapper.val('%s')" % self.name
            else:
                return "mapper.m2o_map(OBJECT_XMLID_PREFIX, mapper.concat('_', 'CSV_COLUMN1','CSV_COLUMN2'))"
        
        elif self.type in ('integer', 'float', 'monetary'):
            return "mapper.num('%s')" % self.get_name()
        elif self.type in ('boolean'):
            return "mapper.bool_val('%s', true_vals=true_values, false_vals=false_values)" % self.get_name()
        elif self.type in ('datetime'):
            return "mapper.val('%s', postprocess=lambda x: datetime.strptime(x, 'CSV_DATE_FORMAT').strftime('%%Y-%%m-%%d 00:00:00'))" % self.get_name()
        elif self.type in ('binary'):
            return "mapper.binary('%s', data_raw_dir)" % self.get_name()
        elif self.type in ('selection'):
            if mapsel:
                return "mapper.map_val('%s', %s_%s_map)" % (self.get_name(), model_mapped_name, self.name)
            else:
                return "mapper.val('%s')" % self.get_name()
        elif self.type in ('many2many') and not wxmlid:
            return "mapper.m2m(PREFIX_%s, '%s')" % (self.relation.replace('.', '_').upper(), self.get_name())
        elif self.type in ('many2one', 'one2many', 'many2many') and not wxmlid:
            return "mapper.m2o(PREFIX_%s, '%s')" % (self.relation.replace('.', '_').upper(), self.get_name())

        else:
            return "mapper.val('%s')" % self.get_name()
    
    def is_required(self):
        return self.required and len(self.default_value) == 0


def load_fields():
    """
    Build the model fields list, fetched as defined in the target database.
    """
    global has_tracked_fields
    global has_computed_fields
    has_tracked_fields, has_computed_fields =  False, False
    connection = conf_lib.get_server_connection(config)
    model_fields = connection.get_model('ir.model.fields')

    field_ids = model_fields.search([('model', '=', model)])
    fields = model_fields.read(field_ids)
    ret = []
    for field in fields:
        f = ModelField(connection, field)
        has_tracked_fields = has_tracked_fields or f.track_visibility
        has_computed_fields = has_computed_fields or len(f.compute) > 1
        ret.append(f)
    return ret
    

def write_begin(file):
    """
    Write the beginning of the generated python script.
    """
    file.write("# -*- coding: utf-8 -*-\n")
    file.write("\n")
    file.write("from odoo_csv_tools.lib import mapper\n")
    file.write("from odoo_csv_tools.lib.transform import Processor\n")
    file.write("from prefix import *\n")
    file.write("from mapping import *\n")
    file.write("from files import *\n")
    file.write("from funclib import *\n")
    file.write("from datetime import datetime\n")
    file.write("\n")
    file.write("# Needed for RPC calls\n")
    file.write("# import odoolib\n")
    file.write("# from odoo_csv_tools.lib import conf_lib\n")
    file.write("# connection = conf_lib.get_server_connection(config_file)\n")
    file.write("\n")
    file.write("def preprocess_%s(header, data):\n" % model_class_name)
    file.write("    # Do nothing\n")
    file.write("    return header, data\n")
    file.write("    #\n")
    file.write("    # Add a column\n")
    file.write("    # header.append('NEW_COLUMN')\n")
    file.write("    # for i, j in enumerate(data):\n")
    file.write("    #     data[i].append(NEW_VALUE)\n")
    file.write("    #\n")
    file.write("    # Keep lines that match a criteria\n")
    file.write("    # data_new = []\n")
    file.write("    # for i, j in enumerate(data):\n")
    file.write("    #     line = dict(zip(header, j))\n")
    file.write("    #     if line['CSV_COLUMN'].....\n")
    file.write("    #         data_new.append(j)\n")
    file.write("    # return header, data_new\n")
    file.write("\n")
    file.write("processor = Processor(src_%s, delimiter='%s', preprocess=preprocess_%s)\n" % (model_mapped_name, csv_delimiter, model_class_name))
    file.write("\n")


def write_end(file):
    """
    Write the end of the generated python script.
    """
    ctx = ''
    ctx_opt = []

    if dbname and not offline:
        if has_tracked_fields:
            ctx_opt.append("'tracking_disable': True")
        if has_computed_fields:
            ctx_opt.append("'defer_fields_computation': True")
        if wmetadata:
            ctx_opt.append("'write_metadata': True")

    if len(ctx_opt):
        ctx = "'context': \"{%s}\", " % ', '.join(ctx_opt)

    # file.write("processor.process(%s, dest_%s, {'model': '%s', %s'groupby': '', 'ignore': '', 'worker': %s, 'batch_size': %s}, 'set', verbose=False)\n\n" % (model_mapping_name, model_mapped_name, model, ctx, default_worker, default_batch_size))
    file.write("processor.process(%s, dest_%s, {'model': '%s', %s'groupby': '', 'worker': %s, 'batch_size': %s}, 'set', verbose=False)\n\n" % (model_mapping_name, model_mapped_name, model, ctx, default_worker, default_batch_size))
    file.write("processor.write_to_file('%s%s', python_exe='%s', path='%s')\n\n" % (model_mapped_name, script_extension, default_python_exe, default_path))


def write_mapping(file):
    """
    Write the fields mapping of the generated python script.
    """
    if not dbname or offline:
        file.write("%s = {\n    'id': ,\n}\n\n" % model_mapping_name)
        return

    fields = load_fields()
    filtering = "lambda f: f.name != '__last_update'"
    if wstored:
        filtering = "%s and f.store" % filtering
    if not wo2m:
        filtering = "%s and f.type != 'one2many'" % filtering
    if not wmetadata:
        filtering = "%s and f.name not in ('create_uid', 'write_uid', 'create_date', 'write_date', 'active')" % filtering
    fields = filter(eval(filtering), fields)
    fields = sorted(fields, key=lambda f: ((f.name != 'id'), not f.is_required(), f.name))
    
    if skeleton == 'dict':
        file.write('%s = {\n' % model_mapping_name)
        for f in fields:
            if verbose: sys.stdout.write('Write field %s\n' % f.name)
            line_start = '# ' if (required and not f.is_required() and f.name != 'id') or f.import_warn_msg else ''
            file.write ("    # %s\n" % f.get_info())
            file.write("    %s'%s': %s,\n" % (line_start,f.get_mapping_name(), f.get_mapper_command().replace('OBJECT_XMLID_PREFIX', 'PREFIX_%s' % model_mapped_name.upper())))
        file.write('}\n\n')
            
    elif skeleton == 'map':
        function_prefix = 'handle_%s_' % model_mapped_name
        for f in fields:
            if verbose: sys.stdout.write('Write map function of field %s\n' % f.name)
            line_start = '# ' if (required and not f.is_required()) or f.import_warn_msg else ''
            file.write ("%sdef %s%s(line):\n" % (line_start, function_prefix, f.name))
            file.write ("%s    return %s(line)\n\n" % (line_start,f.get_mapper_command().replace('OBJECT_XMLID_PREFIX', 'PREFIX_%s' % model_mapped_name.upper())))
        
        file.write('%s = {\n' % model_mapping_name)
        for f in fields:
            if verbose: sys.stdout.write('Write field %s\n' % f.name)
            line_start = '# ' if (required and not f.is_required() and f.name != 'id') or f.import_warn_msg else ''
            file.write ("    # %s\n" % f.get_info())
            file.write ("    %s'%s': %s,\n" % (line_start,f.get_mapping_name(), '%s%s' % (function_prefix, f.name)))
        file.write('}\n\n')

    # Add selection dictionaries if --map-selection
    if mapsel:
        if verbose: sys.stdout.write('Write mapping of selection fields\n')
        if sys.version_info >= (3, 0, 0):
            with open(os.path.join(base_dir, 'mapping.py'), 'a') as pf:
                pf.write("# Selection fields in model %s\n\n" % model)
                for f in filter(lambda x: x.type == 'selection', fields):
                    sys.stdout.write('Write mapping of selection field %s\n' % f.name)
                    line_start = '# ' if (required and not f.is_required()) else ''
                    pf.write("%s%s_%s_map = {\n" % (line_start, model_mapped_name, f.name))
                    for sel in f.selection:
                        key, val = sel.split(selection_sep)
                        pf.write('%s    "%s": %s,\n' % (line_start, val.strip(), key.strip()))
                    pf.write("%s}\n\n" % line_start)
        else:
            with io.open(os.path.join(base_dir, 'mapping.py'), 'a', encoding='utf-8') as pf:
                pf.write("# Selection fields in model %s\n\n" % unicode(model, 'utf-8'))
                for f in filter(lambda x: x.type == 'selection', fields):
                    sys.stdout.write('Write mapping of selection field %s\n' % f.name)
                    line_start = '# ' if (required and not f.is_required()) else ''
                    pf.write("%s%s_%s_map = {\n" % (line_start, model_mapped_name, f.name))
                    for sel in f.selection:
                        key, val = sel.split(selection_sep)
                        pf.write('%s    "%s": %s,\n' % (line_start, val.strip(), key.strip()))
                    pf.write("%s}\n\n" % unicode(line_start, 'utf-8'))


def model_exists(model):
    """
    Return True if 'model' is scaffoldable.
    """
    connection = conf_lib.get_server_connection(config)
    model_model = connection.get_model('ir.model')
    res = model_model.search_count([('model', '=', model), ('transient', '=', False)])
    return res != 0


def scaffold_model():
    """
    Create the python script.
    """
    global offline
    global dbname
    global host
    if sys.version_info >= (3, 0, 0):
        import configparser as ConfigParser
    else:
        import ConfigParser
    cfg = ConfigParser.RawConfigParser({'protocol': 'xmlrpc', 'port': 8069})
    cfg.read(config)
    host = cfg.get('Connection', 'hostname')
    dbname = cfg.get('Connection', 'database')
    login = cfg.get('Connection', 'login')
    uid = cfg.get('Connection', 'uid')

    sys.stdout.write("Using connection file: %s (db: %s, host: %s, login: %s, uid: %s)\n" % (config, dbname, host, login, uid))

    if not dbname:
        offline = True
    elif not model_exists(model):
        sys.stderr.write("Model %s not found\n" % model)
        return
    
    do_file = skeleton or offline

    if os.path.isfile(outfile):
        if force:
            if verbose: sys.stdout.write("Output file %s already exists and will be overwritten.\n" % outfile)
        else:
            sys.stderr.write("The file %s already exists.\n" % outfile)
            do_file = False

    if do_file:
        # Write the file
        with open(outfile, 'w') as of:
            write_begin(of)
            write_mapping(of)
            write_end(of)

        if offline:
            sys.stdout.write("Minimal skeleton code generated in %s%s\n" % (outfile, ' because no database is defined' if not dbname else ''))
        else:
            sys.stdout.write("Skeleton code generated in %s\n" % outfile)
    else:
        sys.stdout.write("Skeleton code not generated. Use option -k|--skeleton or -n|--offline or -f|--force to generate the python script.\n")

    dirname = os.path.dirname(outfile)

    if append:
        #Add command to transform script
        script = os.path.join(dirname, 'transform%s' % script_extension)
        if platform.system() == 'Windows':
            line = "echo Transform %s\npython %s.py > %s\\transform_%s_out.log 2> %s\\transform_%s_err.log\n" % (model_mapped_name, model_mapped_name, '%LOGDIR%', model_mapped_name, '%LOGDIR%', model_mapped_name)
        else:
            os.system('sed -i "$ d" %s' % script)
            line = 'load_script %s\nchmod +x *.sh\n' % model_mapped_name
        with open (script, 'a') as f:
            f.write(line)
        sys.stdout.write('Script %s.py added in %s\n' % (model_mapped_name, script))

        #Add command to load script
        script = os.path.join(dirname, 'load%s' % script_extension)
        if platform.system() == 'Windows':
            line = "echo Load %s\ncall %s%s > %s\\load_%s_out.log 2> %s\\load_%s_err.log\n" % (model_mapped_name, model_mapped_name, script_extension, '%LOGDIR%', model_mapped_name, '%LOGDIR%', model_mapped_name)
        else:
            line = 'load_script %s\n' % (model_mapped_name)
        with open (script, 'a') as f:
            f.write(line)
        sys.stdout.write('Script %s%s added in %s\n' % (model, script_extension, script))

        # Add model to prefix.py
        if not wxmlid:
            script = os.path.join(dirname, 'prefix.py')
            line = "PREFIX_%s = '%s_%s' %s project_name\n" % (model_mapped_name.upper(), '%s', model_mapped_name, '%')
            with open (script, 'a') as f:
                f.write(line)
            sys.stdout.write('Prefix PREFIX_%s added in %s\n' % (model_mapped_name.upper(), script))
        else:
            if verbose: sys.stdout.write('XML_ID prefix not added because of option --with-xmlid\n')
        
        # Add model to files.py
        script = os.path.join(dirname, 'files.py')
        with open (script, 'a') as f:
            f.write("# Model %s\n" % model)
            f.write("src_%s = os.path.join(data_src_dir, '%s.csv')\n" % (model_mapped_name , model_mapped_name))
            f.write("dest_%s = os.path.join(data_dest_dir, '%s.csv')\n" % (model_mapped_name , model))
        sys.stdout.write('%s files added in %s\n' % (model, script))

        # Add model to clean_data.py
        script = os.path.join(dirname, 'clean_data.py')
        # line = "PREFIX_%s = '%s_%s' %s project_name\n" % (model_mapped_name.upper(), '%s', model_mapped_name, '%')
        # line = "delete_xml_id(connection, '%s', '%s_%s' %s (demo, project_name))\n" % (model, '%s', model_mapped_name, '%')
        with open(script, 'a') as f:
            f.write("delete_xml_id(connection, '%s', '%s_%s' %s project_name, demo)\n" % (model, '%s', model_mapped_name, '%'))
        sys.stdout.write('Model %s added in %s\n' % (model, script))
    else:
        sys.stdout.write("You should probably add this model in files.py, prefix.py, clean_data.py, transform%s and load%s with -a|--append\n" % (script_extension, script_extension))


##############################################################################
# OTHER ACTIONS
##############################################################################

def list_models():
    connection = conf_lib.get_server_connection(config)
    model_model = connection.get_model('ir.model')

    models = model_model.search_read([('transient', '=', False), ('model', '!=', '_unknown')], ['model', 'name'])

    if not models:
        sys.stdout.write('No model found !')
        return

    for m in sorted(models, key=lambda f: f['model']):
        sys.stdout.write('%s (%s)\n' % (m['model'], m['name']))


def show_version():
    sys.stdout.write("%s %s\n" % (module_name, module_version))

##############################################################################
# MAIN
##############################################################################

if __name__ == '__main__':
    module_name = os.path.basename(sys.argv[0])
    # f = is_remote_host('pcodoo')
    conf_dir_name = 'conf'
    orig_dir_name = 'origin'
    orig_raw_dir_name = os.path.join(orig_dir_name, 'binary')
    data_dir_name = 'data'
    log_dir_name = 'log'
    selection_sep = ': '
    default_base_dir = os.path.join('.','')


    module_descr = """Version: %s
    Create the structure of an import project and model skeleton codes working 
    with odoo_csv_tools (https://github.com/tfrancoi/odoo_csv_import).

    Functionalities:
    ----------------
    - Create the project structure:
    %s -s -p PATH [-d DBNAME] [-t HOST] [-u USERID] [-f] [-v]

    - Skeleton a model:
    %s -m MODEL [-a] [--map-selection] [--with-xmlid] [-r] [-k map | -n]
                            [--with-one2many] [--with-metadata] [--stored] [-v]
                            [--max-descr MAXDESCR] [-f] [-o OUTFILE] [-c CONFIG]

    - Show available models:
    %s -l [-c CONFIG]
    """ % (module_version, module_name, module_name, module_name)

    module_epilog = """
    More information on https://github.com/jad-odoo/odoo_import_scaffold
    """
    
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=module_descr, epilog=module_epilog)
    parser.add_argument('-s', '--scaffold', dest='scaffold', action='store_true', help='create the folders structure and the basic project files')
    parser.add_argument('-p', '--path', dest='path', default=default_base_dir, required=False, help='project path (default: current dir)')
    parser.add_argument('-d', '--db', dest='dbname', default='', required=False, help='target database. If omitted, it is the first part of HOST')
    parser.add_argument('-t', '--host', dest='host', default='localhost', required=False, help='hostname of the database (default: localhost)')
    parser.add_argument('-u', '--userid', dest='userid', type=int, default=2, required=False, help='user id of RPC calls (default: 2)')
    parser.add_argument('-m', '--model', dest='model', required=False, help='technical name of the model to skeleton (ex: res.partner)')
    parser.add_argument('-c', '--config', dest='config', default=os.path.join(conf_dir_name,'connection.conf'), required=False, help='configuration file (relative to --path) defining the RPC connections parameters (default: %s)' % os.path.join(conf_dir_name, 'connection.conf'))
    parser.add_argument('-o', '--outfile', dest='outfile', required=False, help='python script of the model skeleton code (default: model name with dots replaced by underscores)')
    parser.add_argument('-k', '--skeleton', dest='skeleton', choices=['dict','map'], default='dict', required = False, help='skeleton code type. dict: generate mapping as a simple dictionary. map: create the same dictionary with map functions for each field (default: dict)')
    parser.add_argument('-r', '--required', dest='required',  action='store_true', help='keep only the required fields without default value (comment the optional fields')
    parser.add_argument('--field-name', dest='fieldname', choices=['tech','user'], default='user', required = False, help='Field name in import file. tech=technical name, user=User name (default: user). Generates the mapping accordingly.')
    parser.add_argument('--stored', dest='wstored', action='store_true', help="include only stored fields")
    parser.add_argument('--with-o2m', dest='wo2m', action='store_true', help="include one2many fields")
    parser.add_argument('--with-metadata', dest='wmetadata', action='store_true', help="include metadata fields")
    parser.add_argument('--map-selection', dest='mapsel', action='store_true', help="generate inverse mapping dictionaries (visible value -> technical value) of selection fields in mapping.py")
    parser.add_argument('--with-xmlid', dest='wxmlid', action='store_true', help="assume the client file contains XML_IDs in identifier fields")
    parser.add_argument('--max-descr', dest='maxdescr', default=10, help="limit long descriptions of default value and compute method to MAXDESCR lines (default: 10)")
    parser.add_argument('-n', '--offline', dest='offline', action='store_true', help="don't fetch fields from model. Create a minimal skeleton")
    parser.add_argument('-a', '--append', dest='append', action='store_true', help="add model references to files.py, prefix.py and action scripts")
    parser.add_argument('-f', '--force', dest='force', action='store_true', help='overwrite files and directories if existing.')
    parser.add_argument('-l', '--list', dest='list', action='store_true', help="List installed models in the target Odoo instance")
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='display process information')
    parser.add_argument('--version', dest='version', action='store_true', help='show version')
    
    args = parser.parse_args()

    # Manage params
    scaffold = args.scaffold
    base_dir = args.path
    dbname = args.dbname
    host = args.host
    model = args.model
    userid = args.userid
    config = args.config
    outfile = args.outfile
    required = args.required
    skeleton = args.skeleton
    wstored = args.wstored
    wo2m = args.wo2m
    wmetadata = args.wmetadata
    mapsel = args.mapsel
    wxmlid = args.wxmlid
    maxdescr = int(args.maxdescr)
    offline = args.offline
    append = args.append
    list = args.list
    force = args.force
    verbose = args.verbose
    version = args.version
    fieldname = args.fieldname

    # Do unit actions
    if version:
        show_version()
        sys.exit(0)
    if list:
        list_models()
        sys.exit(0)

    # If no action set, prompt for scaffolding
    action_args = [scaffold, model]
    if not any(action_args):
        if sys.version_info >= (3, 0, 0):
            response = input("Do you want the create the folder structure in %s ? (y|N): " % base_dir)
        else:
            response = raw_input("Do you want the create the folder structure in %s ? (y|N): " % base_dir)
        scaffold = ('Y' == response.upper())

    if not scaffold and not model:
        sys.stderr.write('You need to set an action with -s|--scaffold or -m|--model or -l|--list\n')
        sys.stderr.write('Type %s -h|--help for help\n' % module_name)
        sys.exit(1)

    script_extension = '.cmd' if platform.system() == 'Windows' else '.sh'

    # Do cascaded actions
    if scaffold:
        if base_dir == default_base_dir:
            project_name = os.path.basename(os.path.normpath(os.getcwd()))
        else:
            project_name = os.path.basename(os.path.normpath(base_dir))
        
        conf_dir = os.path.join(base_dir, conf_dir_name)
        orig_dir = os.path.join(base_dir, orig_dir_name)
        orig_raw_dir = os.path.join(base_dir, orig_raw_dir_name)
        data_dir = os.path.join(base_dir, data_dir_name)
        log_dir = os.path.join(base_dir, log_dir_name)

        # If database is omitted, get the first part of the hostname
        if is_remote_host(host) and not dbname:
            dbname = host.split('.')[:1][0]
            sys.stdout.write('Database is set by default to %s.\n' % dbname)

        scaffold_dir()

    if model:
        model_mapped_name = model.replace('.', '_')
        model_class_name = model.title().replace('.', '')
        model_mapping_name = '_'.join(('mapping', model_mapped_name))
        if not outfile:
            outfile = '.'.join((model_mapped_name, 'py'))
        outfile = os.path.join(base_dir,outfile)
        config = os.path.join(base_dir, config)
        csv_delimiter = ';'
        default_worker = 1
        default_batch_size = 10
        default_python_exe = ''
        default_path = ''
        
        scaffold_model()
