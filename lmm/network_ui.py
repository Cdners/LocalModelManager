from PySide6.QtWidgets import QWidget,QFormLayout,QComboBox,QLineEdit,QSpinBox,QLabel,QDialog,QVBoxLayout,QDialogButtonBox,QPushButton,QHBoxLayout
from .i18n import bind,tr,MessageBox
from .network import MODES,save_proxy,parse_proxy,test_connection

class ProxyEditor(QWidget):
    def __init__(self, store, value=None, allow_global=False, parent=None):
        super().__init__(parent); self.store=store; self.saved=value or {'mode':'global' if allow_global else 'system'}
        form=QFormLayout(self); self.mode=QComboBox()
        self.modes = (('global',) if allow_global else ()) + MODES
        self.titles = {'global':'Use global proxy','direct':'Direct','system':'System proxy','http':'HTTP proxy','https':'HTTPS proxy','socks5':'SOCKS5 (local DNS)','socks5h':'SOCKS5H (proxy DNS)'}
        for mode in self.modes:self.mode.addItem(tr(self.titles[mode]),mode)
        self.mode.setCurrentIndex(max(0,self.mode.findData(self.saved.get('mode'))))
        self.url=QLineEdit(); bind(self.url,'Proxy URL (optional)',setter='setPlaceholderText')
        self.host=QLineEdit(self.saved.get('host','')); self.port=QSpinBox(); self.port.setRange(1,65535); self.port.setValue(self.saved.get('port',7890))
        self.username=QLineEdit(self.saved.get('username','')); self.password=QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        bind(self.password,'Leave empty to keep the saved password.',setter='setPlaceholderText')
        for title,widget in [('Proxy mode',self.mode),('Proxy URL',self.url),('Host',self.host),('Port',self.port),('Username (optional)',self.username),('Password (optional)',self.password)]:
            form.addRow(bind(QLabel(),title),widget)
        self.mode.currentIndexChanged.connect(self.sync); self.sync()
    def sync(self):
        custom=self.mode.currentData() not in {'global','direct','system'}
        for w in (self.url,self.host,self.port,self.username,self.password):w.setEnabled(custom)
    def policy(self, persist=True):
        if self.mode.currentData()=='global':return {'mode':'global'}
        data={'mode':self.mode.currentData(),'host':self.host.text().strip(),'port':self.port.value(),
              'username':self.username.text(),'password':self.password.text(),'credential_id':self.saved.get('credential_id','')}
        if self.url.isEnabled():data['url']=self.url.text().strip()
        if not persist: return parse_proxy(data)
        saved = save_proxy(self.store,data)
        self.saved = saved
        self.password.clear(); self.url.clear()
        self.mode.setCurrentIndex(self.mode.findData(saved['mode']))
        self.host.setText(saved.get('host','')); self.port.setValue(saved.get('port',7890))
        self.username.setText(saved.get('username',''))
        return saved
    def refresh_language(self):
        for i,mode in enumerate(self.modes):self.mode.setItemText(i,tr(self.titles[mode]))

class ProxyDialog(QDialog):
    def __init__(self,store,value=None,parent=None):
        super().__init__(parent);bind(self,'Download proxy',setter='setWindowTitle');self.resize(520,360)
        box=QVBoxLayout(self);self.editor=ProxyEditor(store,value,True);box.addWidget(self.editor)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);box.addWidget(buttons)
        for key in ('Save','Cancel'):bind(buttons.button(getattr(QDialogButtonBox.StandardButton,key)),key)
        buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject)
    def save(self):
        try:self.value=self.editor.policy();self.accept()
        except Exception as exc:MessageBox.warning(self,tr('Download proxy'),str(exc))

def add_network_tab(window):
    page=QWidget();layout=QVBoxLayout(page)
    window.network_editor=ProxyEditor(window.store,window.store.settings.get('download_proxy'));layout.addWidget(window.network_editor)
    row=QHBoxLayout();layout.addLayout(row)
    window.network_result=bind(QLabel(),'Applies to metadata, models, runtimes and app updates. Local inference stays direct.')
    window.network_result.setWordWrap(True)
    def test(url):
        try:policy=window.network_editor.policy(False)
        except Exception as exc:window.error(str(exc));return
        window.jobs.submit('Test connection',lambda c,p:test_connection(policy,url),window.network_result.setText,window.error)
    for caption,url in [('Test connection','https://example.com'),('Test Hugging Face','https://huggingface.co/api/models?limit=1'),('Test GitHub','https://api.github.com/rate_limit')]:
        button=bind(QPushButton(),caption);button.clicked.connect(lambda _,u=url:test(u));row.addWidget(button)
    layout.addWidget(window.network_result);layout.addStretch()
    window.settings_tab_names.append('Network');window.settings_tabs.addTab(page,tr('Network'))
