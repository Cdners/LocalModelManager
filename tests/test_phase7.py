from lmm.windows import RUN_NAME, set_autostart


class Registry:
    HKEY_CURRENT_USER=1; KEY_SET_VALUE=2; KEY_QUERY_VALUE=4; REG_SZ=1
    def __init__(self):self.values={"UnrelatedApp":"keep"}
    def CreateKeyEx(self,*args):return self
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def SetValueEx(self,key,name,_,kind,value):self.values[name]=value
    def DeleteValue(self,key,name):
        if name not in self.values:raise FileNotFoundError
        del self.values[name]
    def QueryValueEx(self,key,name):
        if name not in self.values:raise FileNotFoundError
        return self.values[name],1


def test_autostart_quoted_path_repair_and_narrow_delete(tmp_path):
    registry=Registry()
    first=set_autostart(True,tmp_path/"with space",registry)
    assert "--minimized" in first and 'with space"' in first
    second=set_autostart(True,tmp_path/"moved app",registry)
    assert second!=first
    assert set_autostart(False,tmp_path,registry) is None
    assert registry.values=={"UnrelatedApp":"keep"}
