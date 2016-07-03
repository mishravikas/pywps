from abc import ABCMeta, abstractmethod, abstractproperty
import logging
import os
from pywps._compat import urljoin
from pywps.exceptions import NotEnoughStorage, NoApplicableCode, StorageAuthenticationError, StorageDependencyError
from pywps import configuration as config

LOGGER = logging.getLogger(__name__)

class STORE_TYPE:
    PATH = 0
    FTP = 1
    DROPBOX = 2
    GOOGLEDRIVE = 3
# TODO: cover with tests
class StorageAbstract(object):
    """Data storage abstract class
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def store(self, output):
        """
        :param output: of type IOHandler
        :returns: (type, store, url) where
            type - is type of STORE_TYPE - number
            store - string describing storage - file name, database connection
            url - url, where the data can be downloaded
        """
        pass

class DummyStorage(StorageAbstract):
    """Dummy empty storage implementation, does nothing

    Default instance, for non-reference output request

    >>> store = DummyStorage()
    >>> assert store.store
    """

    def __init__(self):
        """
        """

    def store(self, ouput):
        pass


class FileStorage(StorageAbstract):
    """File storage implementation, stores data to file system

    >>> import ConfigParser
    >>> config = ConfigParser.RawConfigParser()
    >>> config.add_section('FileStorage')
    >>> config.set('FileStorage', 'target', './')
    >>> config.add_section('server')
    >>> config.set('server', 'outputurl', 'http://foo/bar/filestorage')
    >>>
    >>> store = FileStorage()
    >>>
    >>> class FakeOutput(object):
    ...     def __init__(self):
    ...         self.file = self._get_file()
    ...     def _get_file(self):
    ...         tiff_file = open('file.tiff', 'w')
    ...         tiff_file.close()
    ...         return 'file.tiff'
    >>> fake_out = FakeOutput()
    >>> (type, path, url) = store.store(fake_out)
    >>> type == STORE_TYPE.PATH
    True
    """

    def __init__(self):
        """
        """
        self.target = config.get_config_value('server', 'outputpath')
        self.output_url = '%s%s' % (
            config.get_config_value('server', 'url'),
            config.get_config_value('server', 'outputurl')
        )

    def store(self, output):
        import shutil, tempfile, math

        file_name = output.file

        file_block_size = os.stat(file_name).st_blksize
        avail_size = get_free_space(self.target)
        file_size = os.stat(file_name).st_size

        # calculate space used according to block size
        actual_file_size = math.ceil(file_size / float(file_block_size)) * file_block_size

        if avail_size < actual_file_size:
            raise NotEnoughStorage('Not enough space in %s to store %s' % (self.target, file_name))

        (prefix, suffix) = os.path.splitext(file_name)
        if not suffix:
            suffix = output.output_format.get_extension()
        (file_dir, file_name) = os.path.split(prefix)
        output_name = tempfile.mkstemp(suffix=suffix, prefix=file_name,
                                       dir=self.target)[1]

        full_output_name  = os.path.join(self.target, output_name)
        LOGGER.info('Storing file output to %s', full_output_name)
        shutil.copy2(output.file, full_output_name)

        just_file_name = os.path.basename(output_name)

        url = urljoin(self.output_url, just_file_name)
        LOGGER.info('File output URI: %s', url)

        return (STORE_TYPE.PATH, output_name, url)


def get_free_space(folder):
    """ Return folder/drive free space (in bytes)
    """
    import platform

    if platform.system() == 'Windows':
        import ctypes

        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(folder), None, None, ctypes.pointer(free_bytes))
        free_space = free_bytes.value
    else:
        free_space = os.statvfs(folder).f_bfree

    LOGGER.debug('Free space: %s', free_space)
    return free_space

class FTPStorage(StorageAbstract):
        def __init__(self):
        """
        """
        self.ftp_host = config.get_config_value('remote-storage', 'ftp_host')
        self.ftp_user = config.get_config_value('remote-storage', 'ftp_user')
        self.ftp_password = config.get_config_value('remote-storage', 'ftp_password')
        self.target = config.get_config_value('server', 'outputpath')
        self.output_url = '%s%s' % (
            config.get_config_value('server', 'url'),
            config.get_config_value('server', 'outputurl')
        )

    def store(self, output):
        import shutil, tempfile

        file_name = output.file
        try:
            import ftplib
        except:
            raise StorageDependecyError('[400]:Dependecny for FTP Storage not met')


        (prefix, suffix) = os.path.splitext(file_name)
        if not suffix:
            suffix = output.output_format.get_extension()
        (file_dir, file_name) = os.path.split(prefix)
        output_name = tempfile.mkstemp(suffix=suffix, prefix=file_name,
                                       dir=self.target)[1]

        full_output_name  = os.path.join(self.target, output_name)
        # LOGGER.info('Storing file output to %s', full_output_name)
        shutil.copy2(output.file, full_output_name)

        ftp = ftplib.FTP(self.ftp_host)
        try:
            ftp.login(self.ftp_user, self.ftp_password)
        except:
            raise StorageAuthenticationError('Invalid FTP credentials')
        ftp.storlines("STOR " + output.file, open(full_output_name))
        just_file_name = os.path.basename(output_name)

        url = urljoin(self.ftp_host, just_file_name)
        LOGGER.info('File Saved in FTP Server: %s', url)

        return (STORE_TYPE.FTP, output_name, url)

class DropBoxStorage(StorageAbstract):
        def __init__(self):
        """
        """
        self.dropbox_app_key = config.get_config_value('remote-storage', 'dropbox_access_token')
        self.target = config.get_config_value('server', 'outputpath')
        self.output_url = '%s%s' % (
            config.get_config_value('server', 'url'),
            config.get_config_value('server', 'outputurl')
        )

    def store(self, output):
        import shutil, tempfile
        try:
            import dropbox
        except:
            raise StorageDependecyError('[400]:Dependecny for Dropbox Storage not met')

        file_name = output.file


        (prefix, suffix) = os.path.splitext(file_name)
        if not suffix:
            suffix = output.output_format.get_extension()
        (file_dir, file_name) = os.path.split(prefix)
        output_name = tempfile.mkstemp(suffix=suffix, prefix=file_name,
                                       dir=self.target)[1]

        full_output_name  = os.path.join(self.target, output_name)
        # LOGGER.info('Storing file output to %s', full_output_name)
        shutil.copy2(output.file, full_output_name)

        client = dropbox.client.DropboxClient(self.dropbox_access_token)
        f = open(full_output_name, 'rb')
        try:
            response = client.put_file(file_name, f)
        except:
            raise StorageAuthenticationError(' [401]:Invalid OAuth2 token for Dropbox.')

        url = client.share(file_name, short_url=False)
        just_file_name = os.path.basename(output_name)

        LOGGER.info('File saved in DropBox: %s', url['url'])

        return (STORE_TYPE.DROPBOX, output_name, url['url'])

class GoogleDriveStorage(StorageAbstract):
    def __init__(self):
        """
        """
        self.drive_secret_file = config.get_config_value('remote-storage', 'drive_secret_file')
        self.target = config.get_config_value('server', 'outputpath')
        self.output_url = '%s%s' % (
            config.get_config_value('server', 'url'),
            config.get_config_value('server', 'outputurl')
        )

    def store(self, output):
        import shutil, tempfile, httplib2
        try:
            from oauth2client.service_account import ServiceAccountCredentials
            from apiclient.discovery import build
        except:
            raise StorageDependecyError('[400]:Dependecny for Google Drive Storage not met')

        file_name = output.file


        (prefix, suffix) = os.path.splitext(file_name)
        if not suffix:
            suffix = output.output_format.get_extension()
        (file_dir, file_name) = os.path.split(prefix)
        output_name = tempfile.mkstemp(suffix=suffix, prefix=file_name,
                                       dir=self.target)[1]

        full_output_name  = os.path.join(self.target, output_name)
        # LOGGER.info('Storing file output to %s', full_output_name)
        shutil.copy2(output.file, full_output_name)
        just_file_name = os.path.basename(output_name)

        local_url = urljoin(self.output_url, just_file_name)

        scopes = 'https://www.googleapis.com/auth/drive.file'
        credentials = ServiceAccountCredentials.from_json_keyfile_name('service-account.json', scopes)
        http = credentials.authorize(httplib2.Http())
        drive_service = build('drive', 'v3', http=http)
        file_metadata = {  'name' : file_name,'mimeType' : 'application/vnd.google-apps.file'}
        media = MediaFileUpload(local_url,mimetype='text/csv',resumable=True)
        drive_service = build('drive', 'v3', http=http)
        uploaded_file = drive_service.files().create(body=file_metadata,media_body=media,fields='id').execute()
        file_id = uploaded_file.get('id')
        new_permission = {'type':'anyone','role':'writer','withLink':True}
        permission = drive_service.permissions().create(fileId=file_id,body=new_permission).execute()
        download_file = drive_service.files().get(fileId=file_id).execute()
        url = download_file['webContentLink']



        return (STORE_TYPE.GOOGLEDRIVE, output_name, url)
