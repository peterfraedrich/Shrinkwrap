#!/usr/bin/env python
## TODO: convert this into a proper python package

from shrinkwrap import shrinkwrap
import yaml
from argparse import ArgumentParser, REMAINDER
from sys import exit


def get_config():
    #### parse arguments
    parser = ArgumentParser(prog='shrinkwrap', description='Configurable intermediary process host for systemd', epilog='Example: $ shrinkwrap --binary httpd --systemd httpd --basedir /usr/bin --extravars @port=80 --environment @user=httpd --command @binary --port @port\n\n')
    parser.add_argument('--binary', '-b', required=False, help='The target binary name that will be run as a child process of this script')
    parser.add_argument('--systemd', '-s', required=False, help='the systemd unit name if different from the binary. If nothing is provided the name of the binary will be used.')
    parser.add_argument('--basedir', '-d', required=False, help='The base directory to look for the target binary')
    parser.add_argument('--environment', '-v', required=False, help='@key=value;@key=value list of pairs of envuronment variables to defined in the thread')
    parser.add_argument('--command', '-c', required=False, nargs=REMAINDER, help='The command to run. The binary should be replaced with @binary to be templated out. Any other variables in --extravars should be represented by @varname and will be replaced at runtime. This should be the last argument given as it will capture everything after it.')
    parser.add_argument('--notifymsg', '-n', required=False, default='READY', help='Sends systemd READY=1 when finding the string in the logs. defaults to "READY"')
    parser.add_argument('--debug', required=False, default=False, action='store_true', help='Puts Shrinkwrap into debug mode; prints out more stuff.')
    args = parser.parse_args()
    if args.systemd == None:
        args.systemd = args.binary
    with open('config.yaml', 'r') as c:
        cf = yaml.load(c.read())
    # map config file to args
    empty_args = []
    config = {}
    for arg in cf:
        if cf[arg] in [None, ''] and args.__dict__[arg] == None:
            empty_args.append(arg)
        elif cf[arg] in [None, ''] and args.__dict__[arg] != None:
            config[arg] = args.__dict__[arg]
        else:
            config[arg] = cf[arg]
    if len(empty_args) > 0:
        print 'ERROR: The following arguments must be defined:'
        for i in empty_args:
            print '- {}'.format(i)
            exit(1)
    return config

if __name__ == '__main__':
    app = shrinkwrap.shrinkwrap(get_config()).start()
