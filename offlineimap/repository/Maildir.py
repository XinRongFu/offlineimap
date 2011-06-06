# Maildir repository support
# Copyright (C) 2002 John Goerzen
# <jgoerzen@complete.org>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

from Base import BaseRepository
from offlineimap import folder
from offlineimap.ui import getglobalui
import os
from stat import *

class MaildirRepository(BaseRepository):
    def __init__(self, reposname, account):
        """Initialize a MaildirRepository object.  Takes a path name
        to the directory holding all the Maildir directories."""
        BaseRepository.__init__(self, reposname, account)

        self.root = self.getlocalroot()
        self.folders = None
        self.ui = getglobalui()
        self.debug("MaildirRepository initialized, sep is " + repr(self.getsep()))
	self.folder_atimes = []

        # Create the top-level folder if it doesn't exist
        if not os.path.isdir(self.root):
            os.mkdir(self.root, 0700)

    def _append_folder_atimes(self, foldername):
	p = os.path.join(self.root, foldername)
	new = os.path.join(p, 'new')
	cur = os.path.join(p, 'cur')
	f = p, os.stat(new)[ST_ATIME], os.stat(cur)[ST_ATIME]
	self.folder_atimes.append(f)

    def restore_folder_atimes(self):
	if not self.folder_atimes:
	    return

	for f in self.folder_atimes:
	    t = f[1], os.stat(os.path.join(f[0], 'new'))[ST_MTIME]
	    os.utime(os.path.join(f[0], 'new'), t)
	    t = f[2], os.stat(os.path.join(f[0], 'cur'))[ST_MTIME]
	    os.utime(os.path.join(f[0], 'cur'), t)

    def getlocalroot(self):
        return os.path.expanduser(self.getconf('localfolders'))

    def debug(self, msg):
        self.ui.debug('maildir', msg)

    def getsep(self):
        return self.getconf('sep', '.').strip()

    def makefolder(self, foldername):
        """Create new Maildir folder if necessary

        :param foldername: A relative mailbox name. The maildir will be
            created in self.root+'/'+foldername. All intermediate folder
            levels will be created if they do not exist yet. 'cur',
            'tmp', and 'new' subfolders will be created in the maildir.
        """
        self.debug("makefolder called with arg '%s'" % (foldername))
        full_path = os.path.abspath(os.path.join(self.root, foldername))
    
        # sanity tests
        if self.getsep() == '/':
            for component in foldername.split('/'):
                assert not component in ['new', 'cur', 'tmp'],\
                    "When using nested folders (/ as a Maildir separator), "\
                    "folder names may not contain 'new', 'cur', 'tmp'."
        assert foldername.find('../') == -1, "Folder names may not contain ../"
        assert not foldername.startswith('/'), "Folder names may not begin with /"

        # If we're using hierarchical folders, it's possible that
        # sub-folders may be created before higher-up ones.
        self.debug("makefolder: calling makedirs '%s'" % full_path)
        try:
            os.makedirs(full_path, 0700)
        except OSError, e:
            if e.errno == 17 and os.path.isdir(full_path):
                self.debug("makefolder: '%s' already a directory" % foldername)
            else:
                raise
        for subdir in ['cur', 'new', 'tmp']:
            try:
                os.mkdir(os.path.join(full_path, subdir), 0700)
            except OSError, e:
                if e.errno == 17 and os.path.isdir(full_path):
                    self.debug("makefolder: '%s' already has subdir %s" %
                               (foldername, sudir))
                else:
                    raise
        # Invalidate the folder cache
        self.folders = None

    def deletefolder(self, foldername):
        self.ui.warn("NOT YET IMPLEMENTED: DELETE FOLDER %s" % foldername)

    def getfolder(self, foldername):
	if self.config.has_option('Repository ' + self.name, 'restoreatime') and self.config.getboolean('Repository ' + self.name, 'restoreatime'):
	    self._append_folder_atimes(foldername)
        return folder.Maildir.MaildirFolder(self.root, foldername,
                                            self.getsep(), self, 
                                            self.accountname, self.config)
    
    def _getfolders_scandir(self, root, extension = None):
        self.debug("_GETFOLDERS_SCANDIR STARTING. root = %s, extension = %s" \
                   % (root, extension))
        # extension willl only be non-None when called recursively when
        # getsep() returns '/'.
        retval = []

        # Configure the full path to this repository -- "toppath"

        if extension == None:
            toppath = root
        else:
            toppath = os.path.join(root, extension)

        self.debug("  toppath = %s" % toppath)

        # Iterate over directories in top & top itself.
        for dirname in os.listdir(toppath) + [toppath]:
            self.debug("  *** top of loop")
            self.debug("  dirname = %s" % dirname)
            if dirname in ['cur', 'new', 'tmp']:
                self.debug("  skipping this dir (Maildir special)")
                # Bypass special files.
                continue
            fullname = os.path.join(toppath, dirname)
            self.debug("  fullname = %s" % fullname)
            if not os.path.isdir(fullname):
                self.debug("  skipping this entry (not a directory)")
                # Not a directory -- not a folder.
                continue
            foldername = dirname
            if extension != None:
                foldername = os.path.join(extension, dirname)
            if (os.path.isdir(os.path.join(fullname, 'cur')) and
                os.path.isdir(os.path.join(fullname, 'new')) and
                os.path.isdir(os.path.join(fullname, 'tmp'))):
                # This directory has maildir stuff -- process
                self.debug("  This is a maildir folder.")

                self.debug("  foldername = %s" % foldername)

		if self.config.has_option('Repository ' + self.name, 'restoreatime') and self.config.getboolean('Repository ' + self.name, 'restoreatime'):
		    self._append_folder_atimes(foldername)
                retval.append(folder.Maildir.MaildirFolder(self.root, foldername,
                                                           self.getsep(), self, self.accountname,
                                                           self.config))
            if self.getsep() == '/' and dirname:
                # Check sub-directories for folders.
                retval.extend(self._getfolders_scandir(root, foldername))
        self.debug("_GETFOLDERS_SCANDIR RETURNING %s" % \
                   repr([x.getname() for x in retval]))
        return retval
    
    def getfolders(self):
        if self.folders == None:
            self.folders = self._getfolders_scandir(self.root)
        return self.folders
    
