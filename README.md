# GOFER
Gofer is a daemon process host designed for running JHipster inside systemd.

### Theory
The idea behind *gofer* is to provide a way to reliably start and stop JHipster systemd services and do some housekeeping tasks on startup. It abstracts the binary name from the systemd unit, allowing you to deploy versioned binaries without the need to update your unit files or startup scripts. Additionally, *gofer* will watch for log outputs and send the systemd READY=1 notification (for use with `Type=notify` units) only when the JHipster app is ready to recieve connections. This avoids instances where your app crashes on startup but systemd doesn't see it as down.

### Usage
` $ ./gofer --binary BINARY --basedir PATH --environment @key=value;@key=value --tempdir PATH --command CMD`

`--binary / -b` the name of the binary (without version) to be run. will be resolved to the latest version in the `basedir`
`--basedir / -d` the base directory to look for the binary in, defaults to the current directory
`--environment / -e` @key=value;@key=value list of pairs of envuronment variables to defined in the thread
`--tempdir / -t` The absolute path of the temp folder to clean before launching the binary; defaults to /app/temp. Anything with the `binary` name in it will be removed prior to running the command
`--command / -c` The command to run. The binary should be replaced with @binary to be templated out. Any other variables in --extravars should be represented by @varname and will be replaced at runtime. This should be the last argument given as it will capture everything after it.

*Example*
```shell
$ gofer --binary registry --basedir /app/microservices --environment @APP_NAME=MBO-AS-DEV;@APP_DC=as --tempdir /app/temp --command java -jar @binary -appname=@APP_NAME -appdc=@APP_DC```

