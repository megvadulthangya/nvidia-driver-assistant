"""System information and distribution detection."""

import os
import logging
import string

from .config import supported_distros


class SystemInfo(object):
    def __init__(self, id, version_id, pretty_name):
        super(SystemInfo, self).__init__()
        self.id = id
        self.original_id = id
        self.version_id = version_id
        self.pretty_name = pretty_name
        self.update_info()

    def update_info(self):
        if self.id in ["opensuse-leap", "opensuse-tumbleweed"]:
            self.id = "opensuse"
        elif self.id in ["cm", "mariner"]:
            self.id = "azurelinux"
        elif self.id in ["rocky", "ol"]:
            self.id = "rhel"
        elif self.id == "arch" and "manjaro" in self.pretty_name.lower():
            self.id = "manjaro"

        if self.id != self.original_id:
            logging.debug("get_distro(): detected %s, setting to %s" % (self.original_id, self.id))


def get_distro(path=None):
    """Get the Linux distribution from /etc/os-release"""
    release_file = "/etc/os-release" if not path else path

    distro_id = None
    version_id = ""
    pretty_name = ""

    if not os.path.exists(release_file):
        logging.error("OS release file not found: %s" % release_file)
        return None

    try:
        with open(release_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith('ID='):
                    distro_id = line.split('=', 1)[1].strip().strip('"')
                elif line.startswith('VERSION_ID='):
                    version_id = line.split('=', 1)[1].strip().strip('"')
                elif line.startswith('PRETTY_NAME='):
                    pretty_name = line.split('=', 1)[1].strip().strip('"')
    except Exception as e:
        logging.error("failed to detect Linux distribution: cannot read %s: %s" % (release_file, e))
        return None

    if not distro_id:
        logging.error("failed to detect Linux distribution: cannot extract valid values from %s" % release_file)
        return None

    system_info = SystemInfo(distro_id, version_id, pretty_name)

    if system_info.id in supported_distros:
        logging.debug(
            "get_distro(): detected %s%s %s distribution is supported"
            % (
                system_info.original_id,
                " (%s)" % system_info.id if system_info.id != system_info.original_id else "",
                system_info.version_id,
            )
        )
        print(
            "Detected system:\n  %s %s\n"
            % (
                (
                    system_info.pretty_name.replace(system_info.version_id, "").strip()
                    if system_info.pretty_name
                    else system_info.id
                ),
                system_info.version_id,
            )
        )
    else:
        logging.debug(
            "get_distro(): detected %s %s distribution is not supported"
            % (system_info.id, system_info.version_id)
        )
        logging.error(
            "Error: detected %s%s %s distribution is not supported"
            % (
                system_info.original_id,
                " (%s)" % system_info.id if system_info.id != system_info.original_id else "",
                system_info.version_id,
            )
        )
        return None

    return system_info


def override_distro(distro_override):
    """Process the --distro argument and return a SystemInfo object"""
    if ":" in distro_override:
        distro_id = distro_override.strip().split(":")[0]
        version_id = distro_override.strip().split(":")[-1]
    else:
        distro_id = distro_override.rstrip(string.digits)
        version_id = distro_override[len(distro_id):]

    return SystemInfo(distro_id, version_id, "")
