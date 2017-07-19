#!/usr/bin/python

#### standard modules
from os import walk, path, listdir, remove, rmdir
from sys import exit
from signal import signal, SIGINT, SIGHUP, SIGQUIT, SIGTERM
from threading import Thread, Lock, current_thread
from fnmatch import fnmatch
from subprocess import Popen, PIPE

#### 3rd party
import sdnotify

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[38;5;33m'
    OKGREEN = '\033[92m'
    WARNING = '\033[38;5;7m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    GRAY = '\033[38;5;7m'

class shrinkwrap:
    '''
    our app class
    '''
    CONSOLE = Lock() # thread-safe console logging!
    THREADS = []
    SIG = False
    NOTIFY = sdnotify.SystemdNotifier()

    def __init__(self, config):
        self.config = config   
        self.DEBUG = config['debug'] 

    def _print_args(self):
        ''' gives us good formatting for logging args'''
        a = {'binary': self.config['binary'],
            'systemd': self.config['systemd'],
            'basedir': self.config['basedir'],
            'environment': self.config['environment'],
            'debug': self.config['debug'],
            'command': self.config['command']}
        return a

    #### set up logging
    def _log(self, message, debug=None):
        '''
        log to stdout to be picked up by journal.
        we dont need to append log levels or anything because were
        just replicating what the tread spits out.
        '''
        if self.DEBUG == True and debug == True:
            print '{}SHRINKWRAP{} [DEBUG]{}: {}{}'.format(bcolors.OKBLUE, bcolors.WARNING, bcolors.GRAY, str(message), bcolors.ENDC)
        elif self.DEBUG != True and debug == True:
            pass
        else:
            print '{}SHRINKWRAP{} [MAIN ]{}: {}'.format(bcolors.OKBLUE, bcolors.OKGREEN, bcolors.ENDC, str(message))

    def _resolve_binary(self, binary, basedir):
        ''' get the name and path of the binary '''
        regex = '*'+binary+'*'
        result = []
        for root, dirs, files in walk(basedir):
            for name in files:
                if fnmatch(name, regex):
                    result.append(path.join(root, name))
        return sorted(result)[len(result) - 1] # return the newest entry in the list

    def _resolve_template(self, binary, cmd_list, env_vars):
        ''' resolve the templated command to an actual command '''
        # flatten command to string
        c = ''
        if isinstance(cmd_list, list):
            c += ' '.join(cmd_list)
        else:
            c += cmd_list
        # sub in binary name
        c = c.replace('@binary', self.real_binary)
        return c

    def _worker_thread(self, command):
        ''' our generic worker thread '''
        sub = Popen(command.split(' '), stdout=PIPE, stderr=PIPE, bufsize=1, env=self.config['environment'])
        while True:
            if self.SIG == True:
                sub.kill()
            line = sub.stdout.readline()
            self.CONSOLE.acquire()
            self._log(line.strip('\n'), False)
            if self.config['notifymsg'] in line:
                self.NOTIFY.notify('READY=1') # tell systemd we're up and running
                self._log('Sent systemd the READY=1 signal. Daemon should show as active/running.', True)
            self.CONSOLE.release()
            if not line:
                self.CONSOLE.acquire()
                self._log('Process in {} exited. Joining thread.'.format(current_thread()), True)
                self.CONSOLE.release()
                self.THREADS.remove(current_thread())
                break
            
    def _spawn_threads(self, command, real_binary):
        ''' creates our threads '''
        thr = Thread(target=self._worker_thread, args=(command,), name=real_binary)
        thr.start()
        self.THREADS.append(thr)

    def _signal_handler(self, signal, frame):
        ''' catches signals and logs them. graceful exits FTW. '''
        SIGNAL_CODES = {
            1 : 'SIGHUP',
            2 : 'SIGINT',
            3 : 'SIGQUIT',
            15 : 'SIGTERM'
        }
        self.CONSOLE.acquire()
        self._log('Caught signal {}'.format(SIGNAL_CODES[signal]), True)
        self.CONSOLE.release()
        self.SIG = True
        for t in self.THREADS:
            t.join()
        self.CONSOLE.acquire()
        self._log('Killed all threads. Exiting gracefully.', True)
        self._log('Threads still running: {}'.format(self.THREADS), True)
        self.CONSOLE.release()
        NOTIFY.notify("STOPPING=1") # tell systemd we're going down
        return

    def start(self):
        self.CONSOLE.acquire()
        self._log('shrinkwrap is starting.', True)
        self._log('Found args: {}'.format(self._print_args()), True)
        self._log('Found environment variables: {}'.format(self.config['environment']), True)
        self.real_binary = self._resolve_binary(self.config['binary'], self.config['basedir'])
        self._log('Resolved binary to {}'.format(self.real_binary), True)
        command = self._resolve_template(self.real_binary, self.config['command'], self.config['environment'])
        self._log('Resolved command to {}'.format(command), True)
        self.CONSOLE.release()
        self._spawn_threads(command, self.real_binary)
        self.CONSOLE.acquire()
        self._log('Spawned threads {}'.format(str(self.THREADS)), True)
        self.CONSOLE.release()
        signal(SIGINT, self._signal_handler)
        signal(SIGHUP, self._signal_handler)
        signal(SIGQUIT, self._signal_handler)
        signal(SIGTERM, self._signal_handler)
        exit(0)




