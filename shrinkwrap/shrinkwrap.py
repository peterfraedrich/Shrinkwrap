#!/usr/bin/python

#### standard modules
from os import walk, path, listdir, remove, rmdir
from sys import exit
#from signal import signal, SIGINT, SIGHUP, SIGQUIT, SIGTERM
from threading import Thread, Lock, current_thread
from fnmatch import fnmatch
from subprocess import Popen, PIPE

#### 3rd party
import sdnotify

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

    def _print_args():
        ''' gives us good formatting for logging args'''
        c = ''
        for i in self.config['args']['command']:
            c += str(i) + ' '
        a = {'binary': self.config['args']['binary'],
            'systemd': self.config['args']['systemd'],
            'basedir': self.config['args']['basedir'],
            'extravars': self.config['args']['extravars'],
            'environment': self.config['args']['environment'],
            'tempdir': self.config['args']['tempdir'],
            'command': c}
        return a

    #### set up logging
    def _log(self, message):
        '''
        log to stdout to be picked up by journal.
        we dont need to append log levels or anything because were
        just replicating what the tread spits out.
        '''
        print '{}'.format(str(message))

    def _split_extra_vars(self, extra_vars):
        ''' splits our extra vars into something we can use '''
        if extra_vars == None:
            return {}
        v = {}
        t = extra_vars.split(';')
        for i in t:
            a = i.split('=')
            v[a[0]] = a[1]
        return v

    def _resolve_binary(binary, basedir):
        ''' get the name and path of the binary '''
        regex = '*'+binary+'*'
        result = []
        for root, dirs, files in walk(basedir):
            for name in files:
                if fnmatch(name, regex):
                    result.append(path.join(root, name))
        print result
        return sorted(result)[len(result) - 1] # return the newest entry in the list

    def _resolve_template(binary, cmd_list, env_vars, extra_vars):
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

    def _worker_thread(command):
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
            
    def _spawn_threads(command, real_binary):
        ''' creates our threads '''
        thr = Thread(target=worker_thread, args=(command,), name=real_binary)
        thr.start()
        THREADS.append(thr)

    def _signal_handler(signal, frame):
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

    def _clean_temp_files(self):
        ''' cleans the /app/temp folder of temp files, if exists '''
        temp_files = listdir(self.config['args']['tempdir'])
        count = 0
        for file in temp_files:
            if self.config['args']['binary'] in file:
                try:
                    remove(path.join(self.config['args']['tempdir'], file))
                    count += 1
                except:
                    rmdir(path.join(self.config['args']['tempdir'], file))
                    count += 1            
        log('Removed {} temp files from {}'.format(count, self.config['args']['tempdir']))
        return

    def start(self):
        self.CONSOLE.acquire()
        self._log('shrinkwrap is starting.')
        self._clean_temp_files()
        self._log('Found args:{}'.format(print_args()))
        real_binary = self._resolve_binary(self.config['args']['binary'], self.config['args']['basedir'])
        self._log('Resolved binary to {}'.format(real_binary))
        extra_vars = self._split_extra_vars(self.config['args']['extravars'])
        self._log('Resolved extra vars to {}'.format(str(extra_vars)))
        command = self._resolve_template(real_binary, self.config['args']['command'], self.config['args']['environment'], extra_vars)
        self._log('Resolved command to {}'.format(command))
        self.CONSOLE.release()
        self._spawn_threads(command, real_binary)
        self.CONSOLE.acquire()
        self._log('Spawned threads {}'.format(str(self.THREADS)))
        self.CONSOLE.release()
        signal(SIGINT, signal_handler)
        signal(SIGHUP, signal_handler)
        signal(SIGQUIT, signal_handler)
        signal(SIGTERM, signal_handler)
        exit(0)




