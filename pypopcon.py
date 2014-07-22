#!/usr/bin/env python

import logging
import os
import platform
import subprocess
import sys
import time
import optparse
try:
    import rpm
except ImportError:
    rpm = False
try:
    import apt
except ImportError:
    apt = False

### logging setup
global_log_level = logging.WARN
console = logging.StreamHandler(sys.stderr)
console.setLevel(logging.WARN)
formatter = logging.Formatter('%(name)s: %(levelname)-8s %(message)s')
console.setFormatter(formatter)
logging.getLogger("pypopcon").addHandler(console)
log = logging.getLogger("pypopcon")
log.debug("Starting log")


def get_options():
    """ command-line options """
    log.debug("in get_options()")

    usage = "usage: %prog -f <FILE> [options]"
    OptionParser = optparse.OptionParser
    parser = OptionParser(usage)

    required = optparse.OptionGroup(parser, "Required")
    optional = optparse.OptionGroup(parser, "Optional")

    optional.add_option("-v", "--verbose", action="store_true", dest="debug", default=False,
                        help="Enable verbose output.")

    parser.add_option_group(required)
    parser.add_option_group(optional)
    options, args = parser.parse_args()

    if options.debug:
        log.setLevel(logging.DEBUG)
        console.setLevel(logging.DEBUG)

    return options


def get_files(package_list = None, provider = None, pkg = None):
    """ method to get a list of files of each package for each package management system (returns a list) """
    log.debug("in get_files(%s, %s, %s)" % (package_list, provider, pkg))

    files_list = []
    if package_list != None and type(package_list) is type({}):
        #a dict of package managers as keys and a list of packages as values has
        #been passed in, so iterate over that
        files_list_dict = {}
        if 'dpkg' in package_list:
            log.debug("'dpkg' determined as a provider in get_files")
            files_list_dict['dpkg'] = {}
            cache = apt.cache.Cache()
            for package in package_list['dpkg']:
                files_list_dict['dpkg'] = files_list + get_dpkg_files(package, cache)
            cache.close()

        if 'rpm' in package_list:
            log.debug("'rpm' determined as a provider in get_files")
            ts = rpm.TransactionSet()
            rpmdb = ts.dbMatch('name')
            files_list = files_list + get_rpm_files(rpmdb, pkg)

    elif provider != None and pkg != None:
        #provider (string) and pkg (list) have both been supplied and
        #package_list (dict) has not, so getting the files for the provided
        #package list from the given provider
        if 'dpkg' in provider:
            log.debug("'dpkg' determined as a provider in get_files")
            files_list = files_list + get_dpkg_files(pkg)

        if 'rpm' in pkg_provider:
            log.debug("'rpm' determined as a provider in get_files")
            ts = rpm.TransactionSet()
            rpmdb = ts.dbMatch('name')
            files_list = files_list + get_rpm_files(rpmdb, pkg)
    else:
        if package_list != None and provider is None and pkg is None:
            log.debug("package_list = %s" % package_list)
            raise ValueError("package_list must be a dict")
        elif package_list is None and provider != None or pkg != None:
            log.debug("provider = %s" % provider)
            log.debug("pkg = %s" % pkg)
            raise ValueError("provider must be a string accompanied by pkg which should be a list")

    log.debug("final file_list is: %s" % files_list)

    return files_list


def get_packages(provider):
    """ get the list of packages for each package provider (returns a dict) """
    log.debug("in get_packages(%s)" % provider)

    packages_list = {}
    if 'dpkg' in provider:
        packages_list['dpkg'] = get_dpkg_packages()

    if 'rpm' in provider:
        packages_list['rpm'] = get_rpm_packages()

    log.debug("final package list is: %s" % packages_list)

    return packages_list


def get_file_stat(pkgfile):
    """ get file stats: mode, inode, device, hard_links, owner_uid, group_uid, byte_size, atime, mtime, ctime """
    log.debug("in get_file_stat(%s)" % pkgfile)

    file_stats = {}
    pkg_file_stat = os.stat(pkgfile)
    #file stats (this needs to be a list of dicts)
    file_stats = {'mode': pkg_file_stat.st_mode,
                  'inode': pkg_file_stat.st_ino,
                  'device': pkg_file_stat.st_dev,
                  'hard_links': pkg_file_stat.st_nlink,
                  'owner_uid': pkg_file_stat.st_uid,
                  'owner_gid': pkg_file_stat.st_gid,
                  'byte_size': int(pkg_file_stat.st_size),
                  'atime': int(pkg_file_stat.st_atime),
                  'mtime': int(pkg_file_stat.st_mtime),
                  'ctime': int(pkg_file_stat.st_ctime),
                  }
    return file_stats


def file_stat(pkgfile):
    """ a function to gracefully handle files in both list and string type """
    log.debug("in file_stat(%s)" % pkgfile)

    if type(pkgfile) == list:
        pkg_files = {}
        for item in pkgfile:
            if os.path.isfile(item):
                pkg_files[item] = get_file_stat(item)
        return pkg_files
    else:
        return get_file_stat(item)


def get_dpkg_packages():
    """ return a list of packages installed on a debian system (returns a list) """
    log.debug("in get_dpkg_packages()")

    dpkg_list = []
    for line in open('/var/lib/dpkg/status').readlines():
        if line.startswith('Package: '):
            dpkg_list.append(line.strip('Package:').strip())

    log.debug("returning list: %s" % dpkg_list)

    return dpkg_list


def get_dpkg_files(pkg, use_cache = None):
    """ return a list of files shipped with a debian package """
    log.debug("in get_dpkg_files(%s)" % pkg)

    if use_cache == None:
        cache = apt.cache.Cache()
    else:
        cache = use_cache

    def _get_the_files(single_pkg):
        log.debug("in get_dpkg_files._get_the_files(%s)" % single_pkg)
        package = cache[single_pkg]
        pkg_file_list = package.installed_files
        log.debug("returning pkg_file_list: %s" % pkg_file_list)
        return pkg_file_list

    if type(pkg) is type(''):
        log.debug('package type is string')
        final_pkg_files_list = _get_the_files(pkg)
    elif type(pkg) is type([]):
        log.debug('package type is list')
        pkg_file_list = []
        for iter_pkg in pkg:
            final_pkg_files_list = pkg_file_list + _get_the_files(iter_pkg)
    else:
        raise ValueError("pkg must be a string or list")

    if use_cache == None:
        cache.close()

    log.debug("returning final_pkg_files_list: %s" % final_pkg_files_list)
    return final_pkg_files_list


def get_rpm_packages():
    """ return a list of files shipped with a rpm package (returns a list) """
    log.debug("in get_rpm_packages()")

    pkg_list = []
    ts = rpm.TransactionSet()
    for pkg in ts.dbMatch('name'):
        pkg_list.append(pkg['name'])

    log.debug("returning list: %s" % pkg_list)

    return pkg_list


def get_rpm_files(rpmdb, pkg):
    """ return a list of files shipped with a rpm package """
    log.debug("in get_rpm_files(%s)" % pkg)

    package = ''
    files = []
    log.debug('searching for %s in rpm database' % pkg)
    for rpmpkg in rpmdb:
        log.debug('current package is %s' % rpmpkg['name'])
        if rpmpkg['name'] == pkg:
            log.debug('found rpmpkg %s matches pkg %s' % (rpmpkg['name'], pkg))
            package = rpmpkg
            break

    if not package:
        log.debug('no packages matched %s' % pkg)

    files = package['FILENAMES']

    log.debug("returning list: %s" % files)

    return files


def get_providers():
    """ return a list of package manamagent systems on the system (referred to as providers) """
    log.debug("in get_providers()")

    providers = []
    if os.path.isdir('/var/lib/dpkg'):
        log.debug('dpkg package manager found (/var/lib/dpkg exists)')
        providers.append('dpkg')
    else:
        log.debug('dpkg package manager not found (/var/lib/dpkg does not exist)')
    if rpm:
        log.debug('rpm package manager found (rpm python module installed)')
        providers.append('rpm')
    else:
        log.debug('rpm package manager not found (rpm python module not installed)')

    return providers


def main():
    options = get_options()

    #set up some easy to reference times
    now = int(time.time())
    daylen = int(24 * 60 * 60)
    monthlen = int(daylen * 30)
    lastmonth = int(now - monthlen)

    installed_pkg_providers = get_providers()

    if not installed_pkg_providers:
        print "No package management system found."
        sys.exit(1)

    pkg_list = get_packages(installed_pkg_providers)

    #ignore any package managers that are installed, but are managing zero packages
    pkg_provider = []
    for provider in installed_pkg_providers:
        if pkg_list[provider]:
            pkg_provider.append(provider)

    #get a list of the files (not dirs) shipped with a package
    pkg_file_list = get_files(pkg_list)

    print pkg_file_list

    for provider in pkg_provider:
        #pkg_stat needs to be a dict where key = rpm/dpkg and value = list of dicts (package => file_list)
        pkg_stat[provider] = {}
        for pkg in pkg_list[provider]:
            pkg_stat[provider][pkg] = {}

            pkg_files = get_files(provider, pkg)
            #get the atime/ctime for the files from the packages
            pkg_stat[provider][pkg]['files'] = file_stat(pkg_files)

    for provider in pkg_provider:
        #iterate over the list of files for each package and check the atime for
        #every file. the most recent atime is the atime for the entire package
        for pkg in pkg_stat[provider]:
            pkgatime_list = []
            pkgctime_list = []
            for pkgfile in pkg_stat[provider][pkg]['files']:
                pkgatime_list.append(pkg_stat[provider][pkg]['files'][pkgfile]['atime'])
                pkgctime_list.append(pkg_stat[provider][pkg]['files'][pkgfile]['ctime'])
            pkg_stat[provider][pkg]['atime'] = 0
            pkg_stat[provider][pkg]['ctime'] = 0
            for atime in pkgatime_list:
                if atime > pkg_stat[provider][pkg]['atime']:
                    pkg_stat[provider][pkg]['atime'] = atime
            for ctime in pkgctime_list:
                if ctime > pkg_stat[provider][pkg]['ctime']:
                    pkg_stat[provider][pkg]['ctime'] = ctime

        for pkg in pkg_stat[provider]:
            #analysis from file stats
            if pkg_stat[provider][pkg]['atime'] < lastmonth:
                pkg_stat[provider][pkg]['analysis'] = '<OLD>'
            elif pkg_stat[provider][pkg]['atime'] > lastmonth and int(pkg_stat[provider][pkg]['atime']) - int(pkg_stat[provider][pkg]['ctime']) < daylen:
                pkg_stat[provider][pkg]['analysis'] = '<RECENT-CTIME>'
            else:
                pkg_stat[provider][pkg]['analysis'] = ''

    #print in reverse order of atime
    for provider in pkg_stat:
        for pkg, atime in sorted(pkg_stat[provider].iteritems(), reverse=True, key=lambda x: x[1]['atime']):
            print '%s %s %s %s' % (pkg_stat[provider][pkg]['atime'], pkg_stat[provider][pkg]['ctime'], pkg, pkg_stat[provider][pkg]['analysis'])


if __name__ == "__main__":
    main()
