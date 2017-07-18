## TODO: convert this into a proper python package

import shrinkwrap
import yaml
from argparse import ArgumentParser, REMAINDER


def get_config():
    #### parse arguments
    parser = ArgumentParser(prog='shrinkwrap', description='Configurable intermediary process host for systemd', epilog='Example: $ shrinkwrap --binary httpd --systemd httpd --basedir /usr/bin --extravars @port=80 --environment @user=httpd --command @binary --port @port\n\n')
    parser.add_argument('--binary', '-b', required=True, help='The target binary name that will be run as a child process of this script')
    parser.add_argument('--systemd', '-s', required=False, help='the systemd unit name if different from the binary. If nothing is provided the name of the binary will be used.')
    parser.add_argument('--basedir', '-d', required=True, help='The base directory to look for the target binary')
    parser.add_argument('--extravars', '-e', required=False, help='@key=value;@key=value list of pairs of variables to pass into the command')
    parser.add_argument('--environment', '-v', required=False, help='@key=value;@key=value list of pairs of envuronment variables to defined in the thread')
    parser.add_argument('--tempdir', '-t', required=False, help='The absolute path of the temp folder to clean before launching the binary; defaults to /app/temp', default='/app/temp')
    parser.add_argument('--command', '-c', required=True, nargs=REMAINDER, help='The command to run. The binary should be replaced with @binary to be templated out. Any other variables in --extravars should be represented by @varname and will be replaced at runtime. This should be the last argument given as it will capture everything after it.')
    parser.add_argument('--notifymsg', '-n', required=False, default='is running! Access URLs:', help='Sends systemd READY=1 when finding the string in the logs. defaults to "is running! Access URLs:"')
    args = parser.parse_args()
    if args.systemd == None:
        args.systemd = args.binary
    with open('config.yaml', 'r') as c:
        config = yaml.load(c.read())
    config['args'] = args.__dict__
    return config

if __name__ == '__main__':
    app = shrinkwrap(get_config())
    app.start()
