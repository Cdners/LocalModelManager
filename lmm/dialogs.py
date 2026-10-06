import json
from dataclasses import asdict
from pathlib import Path

from PySide6.QtWidgets import (QCheckBox,QComboBox,QDialog,QDialogButtonBox,QFileDialog,QFormLayout,
    QGroupBox,QHBoxLayout,QLabel,QLineEdit,QPlainTextEdit,QPushButton,QSpinBox,QVBoxLayout,QWidget,QScrollArea)

from .config import Profile
from .models import match_mmproj
from .adapters import adapters
from .i18n import MessageBox as QMessageBox, bind, tr


class ProfileDialog(QDialog):
    def __init__(self,store,profile=None,parent=None):
        super().__init__(parent); self.store=store; self.original=profile
        self.setWindowTitle(tr("Model profile")); self.resize(760,680)
        profile=profile or Profile("","",runtime_id="",requires_mmproj=False,host=store.settings["default_host"],port=store.settings["default_port"],gpu_layers=store.settings["default_gpu_layers"])
        self.values={}; outer=QVBoxLayout(self);outer.setContentsMargins(18,18,18,18)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content=QWidget();layout=QVBoxLayout(content);layout.setSpacing(18);scroll.setWidget(content);outer.addWidget(scroll)
        self.content_layout=layout
        form=QFormLayout(); form.setVerticalSpacing(12); layout.addLayout(form)
        for key,label in [("id","Profile ID"),("name","Name"),("type","Type"),("runtime_id","Runtime adapter"),("model_path","Model file / directory"),("mmproj_path","MMProj"),("host","Host"),("port","Port")]:
            if key=='runtime_id':
                w=QComboBox();w.addItem(tr('Select runtime explicitly'), '')
                for adapter in adapters().values():
                    w.addItem(adapter.name + ('' if adapter.implemented else ' · ' + tr('Reserved')),adapter.id)
                    if not adapter.implemented:w.model().item(w.count()-1).setEnabled(False)
                w.setCurrentIndex(max(0,w.findData(profile.runtime_id)))
            elif key=="type":
                w=QComboBox()
                for caption,value in [("Speech recognition (ASR)","asr"),("Text generation (LLM)","llm"),("Vision","vision"),("Embedding","embedding"),("Reranker","reranker"),("Text to speech (TTS)","tts")]:w.addItem(tr(caption),value)
                w.setCurrentIndex(w.findData(profile.type))
            elif key=="port":w=QSpinBox(); w.setRange(1,65535); w.setValue(profile.port)
            else:w=QLineEdit(str(getattr(profile,key)))
            self.values[key]=w
            if key in {"model_path","mmproj_path"}:
                row=QWidget(); horizontal=QHBoxLayout(row); horizontal.setContentsMargins(0,0,0,0); horizontal.addWidget(w)
                browse=bind(QPushButton(),"Browse"); browse.clicked.connect(lambda _,k=key:self.browse(k)); horizontal.addWidget(browse); form.addRow(bind(QLabel(),label),row)
            else:form.addRow(bind(QLabel(),label),w)
        self.values["id"].setReadOnly(self.original is not None)
        for key,label in [("requires_mmproj","Requires MMProj"),("auto_start","Allow this profile to start automatically")]:
            w=QCheckBox(); w.setChecked(getattr(profile,key)); self.values[key]=w; form.addRow(bind(QLabel(),label),w)
        self.values['runtime_id'].currentIndexChanged.connect(lambda _:self.values['requires_mmproj'].setChecked(False))
        self.backend=QComboBox()
        for backend in ('cuda','cpu','vulkan','auto'):self.backend.addItem(backend,backend)
        self.backend.setCurrentIndex(self.backend.findData(profile.backend));form.addRow(bind(QLabel(),'Backend'),self.backend)
        toggle=bind(QPushButton(),"Advanced"); toggle.setCheckable(True); layout.addWidget(toggle)
        advanced=QWidget(); extra=QFormLayout(advanced); advanced.hide(); toggle.toggled.connect(advanced.setVisible); layout.addWidget(advanced)
        for key,label,low,high in [("gpu_layers","GPU layers",-1,99999),("parallel","Parallel requests",1,64),("proxy_port","Compatibility proxy port",1,65535)]:
            w=QSpinBox(); w.setRange(low,high); w.setValue(getattr(profile,key)); self.values[key]=w; extra.addRow(bind(QLabel(),label),w)
        w=bind(QCheckBox(),"Only remove the Qwen language …<asr_text> prefix"); w.setChecked(profile.compatibility_proxy)
        self.values["compatibility_proxy"]=w; extra.addRow(bind(QLabel(),"Compatibility Proxy"),w)
        self.args=QPlainTextEdit(json.dumps(profile.extra_args,ensure_ascii=False)); self.args.setMaximumHeight(80); extra.addRow(bind(QLabel(),"Extra arguments (JSON array)"),self.args)
        self.runtime_options=QPlainTextEdit(json.dumps(profile.runtime_options,ensure_ascii=False));self.runtime_options.setMaximumHeight(85)
        extra.addRow(bind(QLabel(),'Runtime options (JSON)'),self.runtime_options)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        for name in ("Save","Cancel"):bind(buttons.button(getattr(QDialogButtonBox.StandardButton,name)),name)
        buttons.accepted.connect(self.accept_profile); buttons.rejected.connect(self.reject); outer.addWidget(buttons)

    def browse(self,key):
        filename,_=QFileDialog.getOpenFileName(self,tr("Select model file"),str(self.store.models),"Model files (*.gguf *.bin *.safetensors *.onnx *.pt);;All files (*)")
        if filename:
            path=Path(filename); self.values[key].setText(self.store.relative(path))
            if key=="model_path":
                matched=match_mmproj(path.name,[p.name for p in path.parent.glob("*.gguf")])
                if matched:self.values["mmproj_path"].setText(self.store.relative(path.parent/matched))
                if not self.values["name"].text():self.values["name"].setText(path.stem)

    def accept_profile(self):
        try:
            values={}
            for key,w in self.values.items():
                if isinstance(w,QCheckBox):values[key]=w.isChecked()
                elif isinstance(w,QSpinBox):values[key]=w.value()
                elif isinstance(w,QComboBox):values[key]=w.currentData()
                else:values[key]=w.text().strip()
            values['backend']=self.backend.currentData()
            values['runtime_options']=json.loads(self.runtime_options.toPlainText())
            if not values['runtime_id']:raise ValueError('Select runtime explicitly; GGUF alone is not a compatibility guarantee.')
            if self.original:
                for key in ('manifest_id','architecture','model_files'):values[key]=getattr(self.original,key)
            values["extra_args"]=json.loads(self.args.toPlainText())
            if not isinstance(values["extra_args"],list):raise ValueError("Extra args must be an array.")
            self.profile=Profile.from_dict(values)
            if self.original is None and any(p.id==self.profile.id for p in self.store.profiles):raise ValueError("Profile ID already exists.")
            if self.profile.host not in {"127.0.0.1","localhost","::1"}:
                if QMessageBox.warning(self,"Network access","This address may allow other devices to access the model API. Continue?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
            self.accept()
        except Exception as exc:QMessageBox.warning(self,"Model profile",str(exc))
