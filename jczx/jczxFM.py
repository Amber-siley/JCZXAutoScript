######################################
#
#       文件相关
#
######################################

from os.path import join,exists,splitext,dirname,basename,isdir,isfile,relpath
from os.path import split as split_path
from os import getcwd,makedirs,unlink,rename,listdir,walk
from zipfile import ZipFile

import shutil
import requests

HEADER = {
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
}

class FileManage:
    def __init__(self,work_path = None, file_path:str = None) -> None:
        if not work_path:
            self.work_path = getcwd()
        else:
            self.work_path = work_path
            if not exists(work_path):
                makedirs(work_path,exist_ok = True)
        if file_path:
            file_infor = splitext(file_path)
            self.file_path = file_path
            self.save_path = dirname(file_path)
            self.file_name = basename(file_path)
            self.file_type = file_infor[-1][1:]
    
    @staticmethod
    def nr_mv(old_path, new_path):
        '''not root move'''
        if not exists(new_path):
            shutil.move(old_path,new_path)
        else:
            FileManage.cp(old_path,new_path)
            FileManage.rm(old_path)
    
    @staticmethod
    def mv(old_path, new_path):
        if isdir(old_path):
            dir = split_path(old_path)[-1]
            new_path = join(new_path,dir)
        FileManage.nr_mv(old_path,new_path)
        
    @staticmethod
    def cp(main_path, aim_path):
        if isdir(main_path):
            shutil.copytree(main_path,aim_path,dirs_exist_ok = True)
        if isfile(main_path):
            shutil.copy(main_path,aim_path)
    
    @staticmethod
    def rm(path):
        if isdir(path):
            shutil.rmtree(path)
        if isfile(path):
            unlink(path)
    
    @staticmethod
    def touch(file_path:str, content = None):
        wp = FileManage(file_path = file_path).save_path
        if not exists(wp):
            makedirs(wp,exist_ok = True)
        if not exists(file_path):
            with open(file_path,"w") as fp:
                fp.write(content)

    def unzip(self, file_path = None, save_path = None, retain:bool = True) ->str:
        file_path = file_path if file_path else self.file_path
        args = (file_path,save_path,retain)
        match FileManage(file_path = file_path).file_type:
            case "zip":
                return self.__unzip(*args)
            case _ as x:
                raise ValueError(f"文件类型 {x} 错误")
    
    def __unzip(self, file_path:str = None, save_path:str = None, retain:bool = True):
        file = ZipFile(file_path)
        if not save_path:
            save_path = relpath(self.work_path,getcwd())
        file_list = file.namelist()
        for _,unzipfile in enumerate(file_list):
            file_info = file.getinfo(unzipfile)
            file_info.filename = self.redecode(file_info.filename)
            file.extract(file_info,save_path)
            
        unzip_file_path = join(self.work_path, file_list[0][:-1])
        if not retain:
            del file
            self.rm(file_path)
        return unzip_file_path
        
    @staticmethod
    def redecode(raw:str) -> str:
        """重新编码，防止中文乱码"""
        try:
            return raw.encode('cp437').decode('gbk')
        except:
            return raw.encode('utf-8').decode('utf-8')
    
    @staticmethod
    def save(content:bytes, save_file_path:str = None):
        with open(save_file_path,"wb") as fp:
            fp.write(content)
    
    @staticmethod
    def rename(src,dst):
        rename(src,dst)
    
    def tree(self) ->list[str]:
        """显示所有文件及其附属文件的路径"""
        return [join(dirpath,file) for dirpath,dirnames,filenames in walk(self.work_path) for file in filenames]
    
    def ls(self) ->list[str]:
        """列出文件"""
        return listdir(self.work_path)
    
    def lsdir(self) -> list[str]:
        """列出文件路径"""
        return [join(self.work_path,path) for path in listdir(self.work_path)]
        
class UrlManage:
    def __init__(self) -> None:
        pass
    
    @staticmethod
    def dowload(d_url:str,save_path = None,file_name = None) ->str:
        '''默认保存在当前工作目录 返回file_path'''
        if not save_path:
            save_path = getcwd()
        if not file_name:
            file_name = d_url.split("/")[-1]
        response = requests.get(d_url,headers = HEADER,stream = True)
        
        save_file_path = join(save_path,file_name)
        data = bytes()
        if response.ok:
            ...
        else:
            raise ConnectionError(d_url)
        for chunk in response.iter_content(1024*1024):
            data += chunk
        FileManage(save_path).save(data,save_file_path)
        return save_file_path
