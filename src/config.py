import os
import sys
import codecs
import logging
import configparser

log = logging.getLogger(__name__)

CONFIG_DIR = "config/"
SERVER_DIR = "servers/"

GLOBAL = "global.ini"
DEFAULT_SERVER = "default.ini"
TEST_SERVER = "test.ini"

class Config:

    def __init__(self, config_dir=CONFIG_DIR, test=False):
        self.test = test
        self.configDir = config_dir
        self.serverDir = self.configDir + SERVER_DIR
        self.configDict = {}
        self.global_setup()

    def global_setup(self):
        globalConfig = self.configDir+GLOBAL
        self.configDict[0] = configparser.SafeConfigParser(os.environ)
        self.configDict[0].read(globalConfig, encoding='utf-8')

    def server_setup(self, servers):
        self.defaultServerConfig = self.configDir+DEFAULT_SERVER
        self.testServerConfig = self.configDir+TEST_SERVER
        
        confFiles = [self.defaultServerConfig,""]
        if self.test: confFiles.append(self.testServerConfig)
        
        self.configDict["default"] = configparser.ConfigParser(interpolation=None)
        self.configDict["default"].read(confFiles, encoding='utf-8')

        for server in servers:
            log.info("Loading config for %s", server.name)
            confFiles[1] = self.serverDir+str(server.id)+".ini"
            self.configDict[server.id] = configparser.ConfigParser(interpolation=None)
            self.configDict[server.id].read(confFiles, encoding='utf-8')
            print({s:dict(self.configDict[server.id].items(s)) for s in self.configDict[server.id].sections()} )

    def get(self, server, section, key):
        try:
            value = self.configDict[server].get(section, key)
        except configparser.NoOptionError:
            log.warn("Could not find {}/{} on {}\n  Missing Option".format(section,key,server))
            return None
        except configparser.NoSectionError:
            log.warn("Could not find {}/{} on {}\n  Missing Section".format(section,key,server))
            return None

        if " " in value:
            return value.split()
        elif value in ['yes','no','true','True','false','False']:
            return self.configDict[server].getboolean(section, key)
        return value

    def put(self, server, section, key, value):
        if isinstance(value, set) or isinstance(value, list):
            value = ' '.join(value)
        log.warn("Modifying {}/{} on {} from {} to {}".format(section,key,server, self.configDict[server].get(section, key), str(value)))
        self.configDict[server].set(section, key, str(value))
        with open(self.serverDir+str(server)+".ini", 'w') as configFile:
            self.configDict[server].write(configFile)
    
    def get_raw(self, server, section, key):
        try:
            value = self.configDict[server].get(section, key)
            return value
        except configparser.NoOptionError:
            log.warn("Could not find {}/{} on {}\n  Missing Option".format(section,key,server))
            return None
        except configparser.NoSectionError:
            log.warn("Could not find {}/{} on {}\n  Missing Section".format(section,key,server))
            return None

    def get_section(self, server, section):
        return self.configDict[server].items(section)



