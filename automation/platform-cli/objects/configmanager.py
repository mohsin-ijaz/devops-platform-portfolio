import os
from lib.io import echo
from objects import registry
from os.path import exists
import configparser


class ConfigManager(object):

    settings = {}

    def check_config_file(self) -> bool:
        echo("Check config", "blue")
        echo(self.settings)
        return True

    def generate_config_file(self):
        echo("Generate config", "blue")
        echo(self.settings)

    def load_config_file(self):
        echo("Load Config File", "blue")
        registry.current_dir = '/Users/ally/Apps/icarcli'
        echo(self.settings)

    def check_paths(self) -> bool:
        echo("Check Paths")
        echo(self.settings)
        return True

    def load_config(self):

        registry.current_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')

        # Read .gitmodules file
        parent_dir = os.path.join(registry.current_dir, "..")
        self.detect_is_git_module(parent_dir)

        registry.dockers_dir = os.path.join(parent_dir, "dockers")
        registry.clouds_dir = os.path.join(parent_dir, "clouds")
        registry.kubectl_dir = os.path.join(parent_dir, "kube")
        registry.kustomize_dir = os.path.join(parent_dir, "kustomize")

        # @todo: moving forward, will try to get away from using git modules, for backwards compatibility
        #           need different paths in case of submodules
        if registry.is_git_module is True:
            registry.kubectl_dir = os.path.join(parent_dir, "kubectl")
            registry.dockers_dir = os.path.join(parent_dir)

        if exists(registry.dockers_dir) is False or exists(registry.kubectl_dir) is False \
                or exists(registry.clouds_dir) is False:

            registry.incomplete_installation_warning = True
            if registry.is_git_module is True:
                echo("Run the following commands\n"
                     "\tgit submodule init && git submodule update\n"
                     "to get the submodules initialized or read about git submodules")
            else:
                echo("One or more of the required repos don't exit in case of using this repo as standalone\n"
                     "\t1. https://bitbucket.org/<GCP_PROJECT>/dockers\n"
                     "\t2. https://bitbucket.org/<GCP_PROJECT>/kube\n"
                     "\t3. https://bitbucket.org/<GCP_PROJECT>/clouds\n", "yellow")

        # @todo: Need to complete this to generate a local .env file so that the above operation to check git module
        #           and set paths not done every time a command runs and simply the config from the config file are
        #           used once its generated. Also it will give the flexibility to have the path and name of the
        #           directories of other projects be different, in case someone wants to clone it elsewhere
        # if not self.check_config_file():
        #     self.generate_config_file()
        # self.load_config_file()
        # if self.check_paths():
        #     echo("Paths are valid")
        # echo("Load Config", "green")
        # echo(self.settings)

        # Set app paths in registry
        registry.config_dir = os.path.join(registry.current_dir, 'config')
        registry.docker_config_dir = os.path.join(registry.dockers_dir, 'project', 'dockers-beta', 'config')
        registry.key_dir = os.path.join(registry.docker_config_dir, 'keys')
        registry.key = os.path.join(registry.key_dir, 'id_rsa')

        echo("Current Dir %s" % registry.current_dir, "blue")
        echo("Config Dir %s" % registry.config_dir, "blue")
        echo("Dockers Dir %s" % registry.dockers_dir, "blue")
        echo("Dockers Config Dir %s" % registry.docker_config_dir, "blue")
        echo("Key Dir %s" % registry.key_dir, "blue")
        echo("Key %s" % registry.key, "blue")
        echo("Kubectl Dir %s" % registry.kubectl_dir, "blue")
        echo("Clouds Dir %s" % registry.clouds_dir, "blue")

    def detect_is_git_module(self, parent_dir):

        git_modules = os.path.join(parent_dir, ".gitmodules")
        git_module_exists = exists(git_modules)
        registry.is_git_module = False
        if git_module_exists:
            config = configparser.ConfigParser()
            config.read(git_modules)
            section = "submodule \"icarcli\""
            option = "url"
            if config.has_section(section) and config.has_option(section, option):
                registry.is_git_module = True
