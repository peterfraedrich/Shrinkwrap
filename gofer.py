#!/usr/bin/python

#### standard modules
from argparse import ArgumentParser, REMAINDER
from os import walk, path, listdir, remove, rmdir
from sys import exit
from signal import signal, SIGINT, SIGHUP, SIGQUIT, SIGTERM
from threading import Thread, Lock, current_thread
from fnmatch import fnmatch
from subprocess import Popen, PIPE

#### 3rd party
import sdnotify

CONSOLE = Lock() # thread-safe console logging!
THREADS = []
SIG = False
NOTIFY = sdnotify.SystemdNotifier()

#### parse arguments
parser = ArgumentParser(prog='gofer', description='Configurable intermediary process host for systemd', epilog='Example: $ gofer --binary httpd --systemd httpd --basedir /usr/bin --extravars @port=80 --environment @user=httpd --command @binary --port @port\n\n')
parser.add_argument('--binary', '-b', required=True, help='The target binary name that will be run as a child process of this script')
parser.add_argument('--systemd', '-s', required=False, help='the systemd unit name if different from the binary. If nothing is provided the name of the binary will be used.')
parser.add_argument('--basedir', '-d', required=True, help='The base directory to look for the target binary')
parser.add_argument('--extravars', '-e', required=False, help='@key=value;@key=value list of pairs of variables to pass into the command')
parser.add_argument('--environment', '-v', required=False, help='@key=value;@key=value list of pairs of envuronment variables to defined in the thread')
parser.add_argument('--tempdir', '-t', required=False, help='The absolute path of the temp folder to clean before launching the binary; defaults to /app/temp', default='/app/temp')
parser.add_argument('--command', '-c', required=True, nargs=REMAINDER, help='The command to run. The binary should be replaced with @binary to be templated out. Any other variables in --extravars should be represented by @varname and will be replaced at runtime. This should be the last argument given as it will capture everything after it.')
parser.add_argument('--notifymsg', '-n', required=False, default='is running! Access URLs:', help='Sends systemd READY=1 when finding the string in the logs. defaults to "is running! Access URLs:"')
args = parser.parse_args()

# if systemd isn't passed, use the binary name
if args.systemd == None:
    args.systemd = args.binary

def print_args():
    ''' gives us good formatting for logging our args'''
    c = ''
    for i in args.command:
        c += str(i) + ' '
    a = {'binary': args.binary,
        'systemd': args.systemd,
        'basedir': args.basedir,
        'extravars': args.extravars,
        'environment': args.environment,
        'tempdir': args.tempdir,
        'command': c}
    return a

#### set up logging
def log(message):
    '''
    log to stdout to be picked up by journal.
    we dont need to append log levels or anything because were
    just replicating what the tread spits out.
    '''
    print '{}'.format(str(message))

def split_extra_vars(extra_vars):
    ''' splits our extra vars into something we can use '''
    if extra_vars == None:
        return {}
    v = {}
    t = extra_vars.split(';')
    for i in t:
        a = i.split('=')
        v[a[0]] = a[1]
    return v

def resolve_binary(binary, basedir):
    ''' get the name and path of the binary '''
    regex = '*'+binary+'*'
    result = []
    for root, dirs, files in walk(basedir):
        for name in files:
            if fnmatch(name, regex):
                result.append(path.join(root, name))
    print result
    return sorted(result)[len(result) - 1] # return the newest entry in the list

def resolve_template(binary, cmd_list, env_vars, extra_vars):
    ''' resolve the templated command to an actual command '''
    # flatten command to string
    c = ''
    for i in cmd_list:
        c += str(i) + ' '
    for k,v in extra_vars.iteritems():
        if k in c:
            c = c.replace(k, v)
    # sub in binary name
    c = c.replace('@binary', real_binary)

    # add env vars to command
    if env_vars == None:
        return c
    env = env_vars.split(';')
    e = ''
    for i in env:
        e += str(i) + ' '
    c = e + ' ' + c
    return c

def worker_thread(command):
    ''' our generic worker thread '''
    sub = Popen(command.split(' '), stdout=PIPE, stderr=PIPE, bufsize=1)
    while True:
        if SIG == True:
            sub.kill()
        line = sub.stdout.readline()
        CONSOLE.acquire()
        log(line.strip('\n'))
        if 'is running! Access URLs:' in line:
            NOTIFY.notify('READY=1') # tell systemd we're up and running
            log('Sent systemd the READY=1 signal. Daemon should show as active/running.')
        CONSOLE.release()
        if not line:
            CONSOLE.acquire()
            log('Process in {} exited. Joining thread.'.format(current_thread()))
            CONSOLE.release()
            THREADS.remove(current_thread())
            break
        
def spawn_threads(command):
    ''' creates our threads '''
    thr = Thread(target=worker_thread, args=(command,))
    thr.start()
    THREADS.append(thr)

def signal_handler(signal, frame):
    ''' catches signals and logs them. graceful exits FTW. '''
    SIGNAL_CODES = {
        1 : 'SIGHUP',
        2 : 'SIGINT',
        3 : 'SIGQUIT',
        15 : 'SIGTERM'
    }
    CONSOLE.acquire()
    log('Caught signal {}'.format(SIGNAL_CODES[signal]))
    CONSOLE.release()
    SIG = True
    for t in THREADS:
        t.join()
    CONSOLE.acquire()
    log('Killed all threads. Exiting gracefully.')
    log('Threads still running: {}'.format(THREADS))
    CONSOLE.release()
    NOTIFY.notify("STOPPING=1") # tell systemd we're going down
    return

def clean_temp_files():
    ''' cleans the /app/temp folder of temp files, if exists '''
    temp_files = listdir(args.tempdir)
    count = 0
    for file in temp_files:
        if args.binary in file:
            try:
                remove(path.join(args.tempdir, file))
                count += 1
            except:
                rmdir(path.join(args.tempdir, file))
                count += 1            
    log('Removed {} temp files from {}'.format(count, args.tempdir))
    return

if __name__ == '__main__':
    CONSOLE.acquire()
    log('GOFER is starting.')
    clean_temp_files()
    log('Found args:{}'.format(print_args()))
    real_binary =  resolve_binary(args.binary, args.basedir)
    log('Resolved binary to {}'.format(real_binary))
    extra_vars = split_extra_vars(args.extravars)
    log('Resolved extra vars to {}'.format(str(extra_vars)))
    command = resolve_template(real_binary, args.command, args.environment, extra_vars)
    log('Resolved command to {}'.format(command))
    CONSOLE.release()
    spawn_threads(command)
    CONSOLE.acquire()
    log('Spawned threads {}'.format(str(THREADS)))
    CONSOLE.release()
    signal(SIGINT, signal_handler)
    signal(SIGHUP, signal_handler)
    signal(SIGQUIT, signal_handler)
    signal(SIGTERM, signal_handler)
    exit(0)




