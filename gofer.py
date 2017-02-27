#!/usr/bin/python

#### standard modules
import argparse
import logging
from systemd.journal import JournalHandler
import os
import sys
import signal
from datetime import datetime as dt
from threading import Thread
import threading
import fnmatch
from subprocess import Popen, PIPE

#### 3rd party
import sdnotify

CONSOLE = threading.Lock() # thread-safe console logging!
THREADS = []
SIGINT = False
NOTIFY = sdnotify.SystemdNotifier()

#### parse arguments
parser = argparse.ArgumentParser(prog='gofer', description='Configurable intermediary process host for systemd', epilog='Example: $ gofer --binary httpd --systemd httpd --basedir /usr/bin --extravars @port=80 --environment @user=httpd --command @binary --port @port\n\n')
parser.add_argument('--binary', '-b', required=True, help='The target binary name that will be run as a child process of this script')
parser.add_argument('--systemd', '-s', required=False, help='the systemd unit name if different from the binary. If nothing is provided the name of the binary will be used.')
parser.add_argument('--basedir', '-d', required=True, help='The base directory to look for the target binary')
parser.add_argument('--extravars', '-e', required=False, help='@key=value,@key=value list of pairs of variables to pass into the command')
parser.add_argument('--environment', '-v', required=False, help='@key=value,@key=value list of pairs of envuronment variables to defined in the thread')
parser.add_argument('--command', '-c', required=True, nargs=argparse.REMAINDER, help='The command to run. The binary should be replaced with @binary to be templated out. Any other variables in --extravars should be represented by @varname and will be replaced at runtime. This should be the last argument given as it will capture everything after it.')
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
    t = extra_vars.split(',')
    for i in t:
        a = i.split('=')
        v[a[0]] = a[1]
    return v

def resolve_binary(binary, basedir):
    ''' get the name and path of the binary '''
    regex = '*'+binary+'*'
    result = []
    for root, dirs, files in os.walk(basedir):
        for name in files:
            if fnmatch.fnmatch(name, regex):
                result.append(os.path.join(root, name))
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
    env = env_vars.split(',')
    e = ''
    for i in env:
        e += str(i) + ' '
    c = e + ' ' + c
    return c

def worker_thread(command):
    ''' our generic worker thread '''
    sub = Popen(command.split(' '), stdout=PIPE, stderr=PIPE, bufsize=1)
    while True:
        if SIGINT == True:
            sub.kill()
        line = sub.stdout.readline()
        CONSOLE.acquire()
        log(line.strip('\n'))
        CONSOLE.release()
        if not line:
            CONSOLE.acquire()
            log('Looks like the process exited. Doing the same.')
            CONSOLE.release()
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
    SIGINT = True
    for t in THREADS:
        t.join()
    CONSOLE.acquire()
    log('Killed all threads. Exiting gracefully.')
    CONSOLE.release()
    NOTIFY.notify("STOPPING=1") # tell systemd we're going down
    return

if __name__ == '__main__':
    CONSOLE.acquire()
    log('Starting up.')
    log('Found args:{}'.format(print_args()))
    real_binary =  resolve_binary(args.binary, args.basedir)
    log('Resolved binary to {}'.format(real_binary))
    extra_vars = split_extra_vars(args.extravars)
    log('Resolved extra vars to {}'.format(str(extra_vars)))
    command = resolve_template(real_binary, args.command, args.environment, extra_vars)
    log('Resolved command to {}'.format(command))
    CONSOLE.release()
    spawn_threads(command)
    NOTIFY.notify('READY=1') # tell systemd we're up and running
    CONSOLE.acquire()
    log('Spawned threads {}'.format(str(THREADS)))
    CONSOLE.release()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)
    signal.signal(signal.SIGQUIT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    sys.exit(0)




