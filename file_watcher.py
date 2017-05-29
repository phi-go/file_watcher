from __future__ import print_function
from builtins import input
import sys
import os
import queue
import pexpect
import time
import yaml
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
if sys.version_info[0] == 2:  # check for python major version
    from backports.shutil_get_terminal_size import get_terminal_size
else:
    from shutil import get_terminal_size

CONFIG_FILE_NAME = '.fw'


class UnknownAnswerException(Exception):
    def __init__(self):
        super(UnknownAnswerException, self).__init__()


class OnModifiedInformer(FileSystemEventHandler):
    def __init__(self, changed_files):
        super(OnModifiedInformer, self).__init__()
        self.changed_files = changed_files

    def on_modified(self, event):
        self.changed_files.put(os.path.relpath(event.src_path))


def get_user_lines_until_empty(msg):
    lines = []
    print(msg)
    while True:
        line = input('> ')
        if line:
            lines.append(line)
        else:
            return lines


def start_watching_for_files(changed_files, path):
    event_handler = OnModifiedInformer(changed_files)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    return observer


def load_config_file():
    # TODO: maybe reload config on change
    try:
        with open(CONFIG_FILE_NAME, 'r') as config_file:
            return yaml.load(config_file)
    except (yaml.YAMLError, IOError) as exc:  # IOError instead of FileNotFoundError to support Python 2.
        return {'commands': [], 'paths': {}}


def reset_commands(config):
    get_new_commands = True
    if config['commands']:
        while True:
            print("Will execute following commands when files are changed:")
            print(str(config['commands']))
            answer = input("Change commands? (y/N) ")
            if answer == 'y':
                break
            elif answer in ['n', '']:
                get_new_commands = False
                break
            else:
                pass
    if get_new_commands:
        command_string = get_user_lines_until_empty(
            "Set commands to execute, each in one line. Empty line if done.")
        config['commands'] = command_string
        print("Will execute following commands when files are changed:")
        print(str(config['commands']))
    return config


def reset_paths(config):
    reset_paths = True
    print(str(config['paths']))
    while True:
        answer = input("Reset paths? (y/N) ")
        if answer == 'y':
            break
        elif answer in ['n', '']:
            reset_paths = False
            break
        else:
            pass
    if reset_paths:
        config['paths'] = {}
    return config


def user_init_config(config):
    config = reset_commands(config)
    config = reset_paths(config)
    return config


def get_path_info(config, path):
    try:
        return config['paths'][path]
    except KeyError:
        return None


def convert_to_path_info(string):
    if string == 'y':
        return {'execute': True, 'cwd': os.getcwd()}
    elif string == 'n':
        return {'execute': None}
    else:
        return None


def set_path_info(config, path):
    user_msg = ("Unknown file changed: " + path +
                "\nRun commands for this path (y/n): ")
    while True:
        answer = input(user_msg)
        path_info = convert_to_path_info(answer)
        if path_info:
            config['paths'][path] = path_info
            break
    return get_path_info(config, path)


def run_command(command):
    child = pexpect.spawn(command)
    child.stderr = sys.stdout
    child.stdout = sys.stdout
    child.interact()


def run_commands(config, path_info):
    # TODO maybe current time and time measurement
    term_columns = get_terminal_size((80, 20)).columns
    sep_string = '='*term_columns
    commands = config['commands']
    print(sep_string)
    for command in commands:
        print(">>>", command, ">>>")
        run_command(command)
        print("<<<")
    print(sep_string)


def act_on_changed_file(config, changed_files):
    path = changed_files.get()  # blocking
    path_info = get_path_info(config, path)
    if not path_info:
        path_info = set_path_info(config, path)
    if path_info['execute']:
        run_commands(config, path_info)


def save_config_to_file(config):
    with open(CONFIG_FILE_NAME, 'w') as config_file:
        yaml.dump(config, config_file)


def main():
    path = os.getcwd()
    changed_files = queue.Queue()
    observer = start_watching_for_files(changed_files, path)
    config = load_config_file()
    config = user_init_config(config)
    print(config)
    while True:
        try:
            print("Running ...:")
            act_on_changed_file(config, changed_files)  # blocking
            # TODO: maybe user input when not running command
        except KeyboardInterrupt:
            break
            # TODO: maybe interrupt command when running and don't stop
            #       but stop when no command is running
    print("\nQuitting, saving config to file:", CONFIG_FILE_NAME)
    observer.stop()
    observer.join()
    save_config_to_file(config)


if __name__ == '__main__':
    main()
