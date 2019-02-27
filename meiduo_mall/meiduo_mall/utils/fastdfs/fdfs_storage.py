# 自定义文件存储类
from django.conf import settings
from django.utils.deconstruct import deconstructible
from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client


@deconstructible
class FDFSStorage(Storage):
    """自定义FDFS文件存储类"""
    def __init__(self, client_conf=None, base_url=None):
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf

        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url = base_url

    def _save(self, name, content):
        """
        name: 上传文件名称
        content: 包含上传文件内容的File对象 content.read()
        """
        # 实现代码: 将文件上传到FDFS系统
        # client = Fdfs_client(settings.FDFS_CLIENT_CONF)
        client = Fdfs_client(self.client_conf)

        response = client.upload_by_buffer(content.read())

        if response.get('Status') != 'Upload successed.':
            raise Exception('上传文件到FDFS系统失败')

        # 获取文件ID
        file_id = response.get('Remote file_id')

        return file_id

    def exists(self, name):
        """
        name: 上传文件名称
        判断文件的名称是否重复
        """
        return False

    def url(self, name):
        """
        获取可以访问到文件的url的完整路径
        name: 表中image字段保存的内容
        """
        # return settings.FDFS_URL + name
        return self.base_url + name