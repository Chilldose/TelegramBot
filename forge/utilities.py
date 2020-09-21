import yaml, json, os, logging, sys
import logging.config
import socket
try:
    import psutil
except:
    pass
import time

l = logging.getLogger("forge_michael")

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def parse_args():

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="The path to the config file for Michael")

    args = parser.parse_args()

    return args

def load_yaml(path):
    """Loads a yaml file and returns the dict representation of it"""
    with open(os.path.normpath(path), 'r') as stream:
        try:
            data = yaml.load(stream, Loader=yaml.FullLoader)
            if isinstance(data, str):
                data = json.loads(data)
            return data
        except yaml.YAMLError as exc:
            l.error("While loading the yml file {} the error: {} happend.".format(path, exc))

class LogFile:
    """
    This class handles the Logfile for the whole framework
    """
    def __init__(self, path='logger.yml', default_level=logging.INFO, env_key='LOG_CFG'):
        """
        Initiates the logfile with the logging level
        :param path: Path to logger file
        :param logging_level: None, debug, info, warning, error critical
        :param env_key: env_key
        """


        value = os.getenv(env_key, None)
        if value:
            path = value
        if os.path.exists(os.path.normpath(path)):
            with open(path, 'rt') as f:
                config = yaml.safe_load(f.read())
                # If directory is non existent create it
            logging.config.dictConfig(config)
        else:
            logging.basicConfig(level=default_level)

        self.log_LEVELS = {"NOTSET": 0, "DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}

        self.welcome_string =  "Welcome to the family! I am Michales litte helper." \
                               " I log everything so you can see what happend, later on."

        # Create a logger Object
        self.LOG = logging.getLogger("Logfile")
        # Print welcome message
        self.LOG.info(self.welcome_string)

# Return CPU temperature as a character string
def getCPUtemperature():
    res = os.popen('vcgencmd measure_temp').readline()
    return res

# Return RAM information (unit=kb) in a list
# Index 0: total RAM
# Index 1: used RAM
# Index 2: free RAM
def getRAMinfo():
    p = os.popen('free')
    i = 0
    while 1:
        i = i + 1
        line = p.readline()
        if i==2:
            return(line.split()[1:4])

# Return % of CPU used by user as a character string
def getCPUuse():
    try:
        import psutil
        return str(psutil.cpu_percent())
    except ModuleNotFoundError:
        return "psutil is not installed. No CPU usage query possible."

# Return information about disk space as a list (unit included)
# Index 0: total disk space
# Index 1: used disk space
# Index 2: remaining disk space
# Index 3: percentage of disk used
def getDiskSpace():
    p = os.popen("df -h /")
    i = 0
    while 1:
        i = i +1
        line = p.readline()
        if i==2:
            return(line.split()[1:5])

def getuptime():
    return time.time() - psutil.boot_time()

if __name__ == "__main__":
    uptime = getuptime()/3600
    temp = getCPUtemperature()
    CPU = getCPUuse()
    RAM = getRAMinfo()
    DISK = getDiskSpace()
