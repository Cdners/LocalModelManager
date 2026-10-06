from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
import uuid

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView,QApplication,QCheckBox,QComboBox,QDialog,QFileDialog,QFormLayout,
    QFrame,QHBoxLayout,QLabel,QLineEdit,QListWidget,QMessageBox,QPlainTextEdit,QProgressBar,QPushButton,
    QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget,QHeaderView)

from . import __version__, api, updater
from .audio import Recorder, write_wav
from .config import Profile, atomic_json, read_json
from .dialogs import ProfileDialog
from .downloads import Downloads
from .gpu import Monitor
from .jobs import Control
from .models import Models, RECOMMENDED_REPO, match_mmproj
from .polling import Poller
from .processes import Manager
from .runtime import Runtime
from .windows import TokenStore, set_autostart
from .i18n import MessageBox as QMessageBox, bind, tr


def size(value):
    if value is None:return "—"
    return f"{value/1024**3:.2f} GiB" if value>=1024**3 else f"{value/1024**2:.1f} MiB"


def label(text="",name=None):
    widget=QLabel(); widget.setWordWrap(True)
    if text:bind(widget,text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    if name:widget.setObjectName(name)
    return widget


def buttons(*specs):
    row=QHBoxLayout()
    for text,callback in specs:
        button=bind(QPushButton(),text); button.clicked.connect(callback); row.addWidget(button)
    row.addStretch(); return row


def table(headers):
    widget=QTableWidget(0,len(headers)); widget._translated_headers=headers
    widget.setHorizontalHeaderLabels([tr(text) for text in headers])
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.verticalHeader().hide(); widget.verticalHeader().setDefaultSectionSize(40)
    widget.setAlternatingRowColors(True); widget.setShowGrid(False)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    widget.horizontalHeader().setSectionResizeMode(1 if headers[0]=="Select" else 0,QHeaderView.ResizeMode.Stretch)
    widget.setMinimumHeight(190)
    return widget


class ApplicationPages:
    def build_workspace(self):
        from .network import configure
        from .registry import ModelRegistry
        configure(self.store)
        self.registry=ModelRegistry(self.store)
        self.manager=Manager(self.store); self.runtime=Runtime(self.store)
        self.tokens=TokenStore(self.store); self.models=Models(self.store,self.tokens.get)
        self.downloads=Downloads(self.store); self.download_jobs={}; self.download_callbacks={}
        self.monitor=Monitor(); self.poller=Poller(self.polled,self)
        self.profile_states={}; self.profile_jobs={}; self.gpu_state={}; self.tick_count=0
        self.runtime_busy=False; self.model_update_busy=False; self.last_metadata=None
        self.runtime_latest=read_json(self.store.config/"runtime_latest.json",{})
        self.model_updates=read_json(self.store.config/"model_updates.json",[])
        self.app_latest=read_json(self.store.config/"app_latest.json",{})
        self.log_offsets={}; self.logs_paused=False
        self.recorder=Recorder(self); self.recorder.limit_reached.connect(self.stop_recording)
        self.record_started=None
        self.build_dashboard(); self.build_models(); self.build_downloads(); self.build_runtime()
        self.build_integration(); self.build_logs(); self.extend_settings()
        self.refresh_profiles(); self.refresh_runtime(); self.refresh_installed(); self.refresh_downloads()
        self.timer=QTimer(self); self.timer.setInterval(1000); self.timer.timeout.connect(self.tick)
        self.clock_timer=QTimer(self); self.clock_timer.setInterval(100); self.clock_timer.timeout.connect(self.record_clock)

    def activate(self):
        from .tray import Tray
        self.tray=Tray(self)
        self.timer.start(); self.tick()
        def recover(control,progress):
            if self.store.settings["start_with_windows"]:set_autostart(True,self.store.root)
            from .adapters import adapters
            for adapter in adapters().values():
                if adapter.implemented:Runtime(self.store,adapter).recover(self.manager)
            self.models.recover(self.manager)
        def restored(_):
            self.refresh_profiles()
            resume=read_json(self.store.config/"resume_profiles.json",[])
            (self.store.config/"resume_profiles.json").unlink(missing_ok=True)
            if resume:
                for identity in resume:self.service("start",identity)
            elif self.store.settings["start_profiles"]:self.start_auto_profiles()
            QTimer.singleShot(1200,self.daily_checks)
        self.jobs.submit("Recovering services",recover,restored,self.error)

    def card(self,page):
        card=QFrame(); card.setObjectName("card"); box=QVBoxLayout(card); box.setContentsMargins(22,20,22,20); box.setSpacing(14)
        (self.pages[page] if isinstance(page,str) else page).addWidget(card); return box

    def build_dashboard(self):
        row=QHBoxLayout(); row.setSpacing(18); self.pages["Dashboard"].addLayout(row)
        box=self.card(row); box.addWidget(label("Active service","section"))
        self.profile_combo=QComboBox(); self.profile_combo.currentIndexChanged.connect(self.selected_profile); box.addWidget(self.profile_combo)
        self.state_label=label(); box.addWidget(self.state_label)
        self.profile_detail=label(name="subtitle"); box.addWidget(self.profile_detail)
        actions=QHBoxLayout(); self.service_buttons={}
        for verb,title in [("start","Start service"),("stop","Stop"),("restart","Restart")]:
            button=bind(QPushButton(),title); button.setProperty("primary",verb=="start")
            button.clicked.connect(lambda _,v=verb:self.use_selected_model() if v=='start' else self.service(v)); actions.addWidget(button); self.service_buttons[verb]=button
        box.addLayout(actions)
        actions=buttons(("New",self.new_profile),("Edit",self.edit_profile),("Clone",self.clone_profile),("Delete",self.delete_profile))
        for index in range(actions.count()-1):actions.itemAt(index).widget().setProperty("quiet",True)
        box.addLayout(actions)
        box=self.card(row); box.addWidget(label("Graphics card","section"))
        self.gpu_label=label("GPU · Reading…","section"); box.addWidget(self.gpu_label); box.addStretch()
        box.addWidget(label("Memory usage","subtitle")); self.vram_label=label("—","metric"); box.addWidget(self.vram_label)
        self.vram_bar=QProgressBar(); self.vram_bar.setRange(0,100); self.vram_bar.setTextVisible(False); self.vram_bar.setFixedHeight(8); box.addWidget(self.vram_bar)
        self.gpu_detail=label(name="subtitle"); box.addWidget(self.gpu_detail); box.addStretch()
        box.addWidget(label("Total GPU usage across all apps.","subtitle"))
        row.setStretch(0,3); row.setStretch(1,2)
        box=self.card("Dashboard"); box.addWidget(label("App connection","section"))
        self.api_label=label(name="subtitle"); box.addWidget(self.api_label)
        form=QFormLayout(); form.setVerticalSpacing(14)
        self.base_label=label(name="code"); self.id_label=label(name="code")
        for title,widget,caption,callback in [("Base URL",self.base_label,"Copy Base URL",self.copy_base),("Model ID",self.id_label,"Copy Model ID",self.copy_model)]:
            line=QHBoxLayout(); line.addWidget(widget,1); button=bind(QPushButton(),caption); button.clicked.connect(callback); line.addWidget(button)
            form.addRow(label(title,"subtitle"),line)
        box.addLayout(form)
        box=self.card("Dashboard"); line=QHBoxLayout(); line.addWidget(label("Quick actions","section")); line.addStretch()
        line.addLayout(buttons(("Install Qwen3 ASR",self.setup_qwen),("Test microphone",lambda:self.nav.setCurrentRow(4)))); box.addLayout(line)
        box.addWidget(label("A quick setup for local speech recognition.","subtitle"))
        self.pages["Dashboard"].addStretch()

    def current_profile(self):
        identity=self.profile_combo.currentData()
        return next((p for p in self.store.profiles if p.id==identity),None)

    def refresh_profiles(self,selected=None):
        identity=selected or self.profile_combo.currentData() or self.store.settings.get("active_profile")
        self.profile_combo.blockSignals(True); self.profile_combo.clear()
        for profile in self.store.profiles:self.profile_combo.addItem(profile.name,profile.id)
        configured={p.manifest_id or p.id for p in self.store.profiles}
        for manifest in self.registry.entries.values():
            if manifest['id'] not in configured:
                self.profile_combo.addItem(manifest['name']+' · '+tr('Not configured'),'catalog:'+manifest['id'])
        index=self.profile_combo.findData(identity)
        if index>=0:self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False); self.selected_profile()
        if hasattr(self,"log_source"):
            selection=self.log_source.currentData(); self.log_source.clear(); self.log_source.addItem(tr("All services"),"all"); self.log_source.addItem(tr("Application"),"app")
            for profile in self.store.profiles:self.log_source.addItem(profile.name,profile.id)
            index=self.log_source.findData(selection)
            if index>=0:self.log_source.setCurrentIndex(index)

    def selected_profile(self,*_):
        profile=self.current_profile()
        if profile and self.store.settings.get("active_profile")!=profile.id:
            self.store.settings["active_profile"]=profile.id; self.store.save()
        self.render_state()

    def use_selected_model(self):
        selected=self.profile_combo.currentData() or ''
        if selected.startswith('catalog:'):
            self.install_manifest(selected[8:],activate=True)
        else:
            from .adapters import get_adapter
            profile=self.current_profile()
            if profile and not get_adapter(profile.runtime_id).executable(self.store).exists() and (profile.manifest_id or profile.id) in self.registry.entries:
                self.install_manifest(profile.manifest_id or profile.id,activate=True)
            else:self.service('switch')

    def new_profile(self):
        dialog=ProfileDialog(self.store,parent=self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.store.put_profile(dialog.profile); self.refresh_profiles(dialog.profile.id)

    def profile_editable(self,profile):
        busy=self.profile_jobs.get(profile.id)
        if self.runtime_busy or self.model_update_busy or (busy and self.jobs.items[busy]["state"] in {"Running","Pausing"}) or self.profile_states.get(profile.id,{}).get("state") in {"RUNNING","READY","STARTING","LOADING MODEL","STOPPING"}:
            self.error("Stop the service and wait for updates to finish before editing or deleting its profile."); return False
        return True

    def edit_profile(self):
        profile=self.current_profile()
        if not profile or not self.profile_editable(profile):return
        dialog=ProfileDialog(self.store,profile,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.store.put_profile(dialog.profile); self.refresh_profiles(profile.id)

    def clone_profile(self):
        profile=self.current_profile()
        if not profile:return
        data=asdict(profile); data.update(id=profile.id[:65]+"-"+uuid.uuid4().hex[:6],name=profile.name+" copy",port=min(65535,profile.port+2),proxy_port=min(65535,profile.proxy_port+2),auto_start=False)
        self.store.put_profile(Profile.from_dict(data)); self.refresh_profiles(data["id"]); self.edit_profile()

    def delete_profile(self):
        profile=self.current_profile()
        if not profile or not self.profile_editable(profile):return
        if QMessageBox.question(self,"Delete profile",tr("Delete the configuration for {name}? Model files will be kept.",name=profile.name))!=QMessageBox.StandardButton.Yes:return
        self.store.profiles=[p for p in self.store.profiles if p.id!=profile.id]; self.store.save(); self.refresh_profiles()

    def service(self,verb,identity=None,done=None):
        profile=next((p for p in self.store.profiles if p.id==identity),None) if identity else self.current_profile()
        if not profile:self.error("Create a profile first."); return
        if self.runtime_busy or self.model_update_busy or getattr(self,'switch_busy',False):self.error("An update is in progress. Please wait."); return
        identity=profile.id
        previous=self.profile_jobs.get(identity)
        if previous and self.jobs.items[previous]["state"]=="Running":
            if verb=="stop":self.jobs.cancel(previous)
            else:self.statusBar().showMessage(tr("An operation is already running for this profile.")); return
        self.profile_states[identity]={"state":"STOPPING" if verb=="stop" else "STARTING"}; self.render_state()
        def action(control,progress):
            control.check()
            if verb=='switch':return self.manager.switch(identity,control,progress)
            if verb=="stop":self.manager.stop(identity); return {"state":"STOPPED"}
            if verb=="restart":self.manager.stop(identity)
            record=self.manager.start(identity)
            ready=api.wait_ready(profile,lambda:self.manager.is_running(identity),control=control,progress=progress)
            return record | ready
        def complete(value):
            self.switch_busy=False
            self.profile_states[identity]=value; self.render_state()
            if done:done(value)
        def failure(message):
            self.switch_busy=False
            self.statusBar().showMessage(message); self.error(message)
        if verb=='switch':self.switch_busy=True
        self.profile_jobs[identity]=self.jobs.submit(verb+" · "+profile.name,action,complete,failure)

    def start_auto_profiles(self):
        for profile in self.store.profiles:
            if profile.auto_start:self.service("start",profile.id)

    def stop_all(self):
        for key in self.profile_jobs.values():
            if self.jobs.items[key]["state"]=="Running":self.jobs.cancel(key)
        self.jobs.submit("Stopping managed services",lambda c,p:self.manager.stop_all(),lambda _:self.tick(),self.error)

    def render_state(self):
        profile=self.current_profile()
        selected=self.profile_combo.currentData() or ''
        catalog=selected.startswith('catalog:')
        state=self.profile_states.get(profile.id,{}) if profile else {}
        text=state.get("state","STOPPED"); self.state_label.setText("●  "+tr(text))
        self.state_label.setStyleSheet("font-size:25px;font-weight:650;color:"+("#087f72" if text=="READY" else "#7a8996"))
        if profile:bind(self.profile_detail,"Port {port}  ·  PID {pid}  ·  {kind}",port=profile.port,pid=state.get("pid","—"),kind=profile.type.upper())
        elif catalog:bind(self.profile_detail,'Install this model and its runtime, then switch the active service.')
        else:bind(self.profile_detail,"Create a profile to start your first model service.")
        busy=text in {"STARTING","STOPPING","LOADING MODEL"}
        for verb,button in self.service_buttons.items():
            allowed=(text in {"READY","RUNNING","STARTING","LOADING MODEL"}) if verb=="stop" else (not busy and (text not in {"READY","RUNNING"} if verb=="start" else text in {"READY","RUNNING"}))
            button.setEnabled(bool(profile) and allowed)
        bind(self.service_buttons['start'],'Install and switch' if catalog else 'Switch to this model')
        if catalog:
            from .adapters import get_adapter
            manifest=self.registry.entries[selected[8:]]
            self.service_buttons['start'].setEnabled(get_adapter(manifest['runtime']['recommended']).implemented and not self.runtime_busy and not getattr(self,'switch_busy',False))
            self.state_label.setText('●  '+tr('Not configured'))
        def mark(key):return tr("Passed") if state.get(key) else tr("Pending")
        bind(self.api_label,"Health {health}     Model list {models}     Transcription {transcription}",health=mark("health"),models=mark("models"),transcription=mark("transcription"))
        ids=state.get("model_ids",[]); ready=text=="READY"
        self.base_label.setText(api.base_url(profile,True) if profile else "")
        connection_id=api.connection_model_id(profile,ids) if profile else ''
        self.id_label.setText(connection_id or tr("Waiting for the service"))
        if hasattr(self,"integration_text"):
            if profile and profile.type=="asr" and ready:
                source="Provider: Local / Custom Whisper\nBase URL: {url}\nModel: {model}\nAPI key: leave empty\n\nThe gateway follows the model selected in the manager." if profile.compatibility_proxy else "Provider: Local / Custom Whisper\nBase URL: {url}\nModel: {model}\nAPI key: leave empty\n\nThe model ID is read from your running service."
                bind(self.integration_text,source,url=api.base_url(profile,True),model=connection_id)
            else:bind(self.integration_text,"Select an ASR profile and start the service to see its connection settings.")

    def copy_base(self):
        profile=self.current_profile()
        if profile:QApplication.clipboard().setText(api.base_url(profile,True)); self.statusBar().showMessage(tr("Copied to clipboard"),3000)

    def copy_model(self):
        profile=self.current_profile(); ids=self.profile_states.get(profile.id,{}).get("model_ids",[]) if profile else []
        if ids:QApplication.clipboard().setText(api.connection_model_id(profile,ids)); self.statusBar().showMessage(tr("Copied to clipboard"),3000)
        else:self.error("No model ID has been returned by /v1/models yet.")

    def build_models(self):
        box=self.card("Models"); box.addWidget(label("Model Registry","section"))
        self.catalog_selector=QComboBox();self.refresh_catalog();box.addWidget(self.catalog_selector)
        box.addLayout(buttons(("Download and configure",lambda:self.install_manifest(self.catalog_selector.currentData())),("Import manifest",self.import_manifest)))
        self.repo_input=QLineEdit(RECOMMENDED_REPO); bind(self.repo_input,"Model source / search keywords",setter="setPlaceholderText")
        self.pages["Models"].addWidget(self.repo_input)
        self.pages["Models"].addLayout(buttons(("Resolve source",self.load_repo),("Search Hugging Face",self.search_models),("Local file",lambda:self.import_local(False)),("Local directory",lambda:self.import_local(True))))
        self.search_results=QListWidget(); self.search_results.setMaximumHeight(130); self.search_results.hide()
        self.search_results.itemActivated.connect(lambda item:(self.repo_input.setText(item.text()),self.load_repo()))
        self.pages["Models"].addWidget(self.search_results)
        self.repo_note=label(); self.pages["Models"].addWidget(self.repo_note)
        self.repo_table=table(["Select","Model file","Size","Type"]); self.repo_table.itemChanged.connect(self.match_selected)
        self.repo_table.hide()
        self.pages["Models"].addWidget(self.repo_table)
        self.download_selected_button=bind(QPushButton(),"Download selected"); self.download_selected_button.clicked.connect(self.download_selected); self.download_selected_button.hide()
        self.pages["Models"].addWidget(self.download_selected_button,0,Qt.AlignmentFlag.AlignLeft)
        self.pages["Models"].addWidget(label("Installed models","section"))
        self.installed_table=table(["Model","Size","Revision","Status"]); self.pages["Models"].addWidget(self.installed_table)
        self.models_empty=label("No models installed yet. Import a model source or choose a catalog entry.","subtitle"); self.pages["Models"].addWidget(self.models_empty)
        self.model_update_label=label(); self.pages["Models"].addWidget(self.model_update_label)
        self.pages["Models"].addLayout(buttons(("Check model updates",self.check_model_updates),("Apply model updates",self.update_models),("Open model folder",lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.models))))))

    def search_models(self):
        query=self.repo_input.text().strip()
        def complete(results):
            self.search_results.clear(); self.search_results.addItems([r.get("id",r.get("modelId","")) for r in results]); self.search_results.show()
            bind(self.repo_note,"Double-click a result to list its model files." if results else "No matching model repositories found.")
        self.jobs.submit("Search Hugging Face",lambda c,p:self.models.search(query,c),complete,self.error)

    def load_repo(self):
        repo=self.repo_input.text().strip()
        from .sources import Sources
        def complete(metadata):
            if metadata.get('source')=='local':self.show_local_import(metadata)
            else:self.show_repo(metadata)
        self.jobs.submit("Resolve source",lambda c,p:Sources(self.models).resolve(repo,c),complete,self.error)

    def show_repo(self,metadata):
        self.repo_table.show(); self.download_selected_button.show()
        self.last_metadata=metadata; self.repo_table.blockSignals(True); self.repo_table.setRowCount(len(metadata["files"]))
        for row,item in enumerate(metadata["files"]):
            check=QTableWidgetItem(); check.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable); check.setCheckState(Qt.CheckState.Unchecked)
            self.repo_table.setItem(row,0,check)
            for col,value in enumerate([item["filename"],size(item["size"]),"MMProj" if item["is_mmproj"] else tr("Model")],1):self.repo_table.setItem(row,col,QTableWidgetItem(value))
        self.repo_table.blockSignals(False); bind(self.repo_note,"Revision {revision} · Matching MMProj files are selected automatically.",revision=metadata["revision"][:12])
        self.repo_note.setText(self.compatibility_text(metadata))
        for i, item in enumerate(metadata['files']):
            if item['filename'] in metadata.get('suggested_files',[]):self.repo_table.item(i,0).setCheckState(Qt.CheckState.Checked)

    def compatibility_text(self,metadata):
        matches=self.registry.match(metadata)
        task=metadata.get('task') or (matches[0]['task'] if matches else tr('Unknown'))
        rows=self.registry.compatibility(metadata)
        details=[tr('Task')+': '+task, tr('Architecture')+': '+(metadata.get('architecture') or tr('Unknown')),
                 tr('Format')+': '+(metadata.get('format') or ', '.join(sorted({Path(f['filename']).suffix.lstrip('.') for f in metadata['files']})))]
        if metadata.get('quantization'):details.append(metadata['quantization'])
        return ' · '.join(details)+'\n'+tr('Compatible runtime')+'\n'+'\n'.join({'compatible':'✓ ','incompatible':'✗ ','unknown':'? '}[r['status']]+r['name']+(' — '+tr('Recommended') if r['recommended'] else '') for r in rows)

    def match_selected(self,item):
        if item.column()!=0 or item.checkState()!=Qt.CheckState.Checked or not self.last_metadata:return
        info=self.last_metadata["files"][item.row()]
        if info["is_mmproj"]:return
        filenames=[f["filename"] for f in self.last_metadata["files"]]
        matched=match_mmproj(info["filename"],filenames)
        if matched:self.repo_table.item(filenames.index(matched),0).setCheckState(Qt.CheckState.Checked)

    def download_selected(self):
        if not self.last_metadata:return
        selected=[f["filename"] for i,f in enumerate(self.last_metadata["files"]) if self.repo_table.item(i,0).checkState()==Qt.CheckState.Checked]
        if not selected:self.error("Select at least one model file."); return
        self.queue_download("model","Download models",{"metadata":self.last_metadata,"filenames":selected})

    def refresh_catalog(self):
        self.catalog_selector.clear()
        for manifest in self.registry.entries.values():self.catalog_selector.addItem(manifest['name'],manifest['id'])
        if hasattr(self,'profile_states') and hasattr(self,'log_source'):self.refresh_profiles()

    def import_manifest(self):
        filename,_=QFileDialog.getOpenFileName(self,tr('Import manifest'),'', 'Manifest (*.yaml *.yml *.json)')
        if not filename:return
        try:
            manifest=self.registry.import_file(filename);self.refresh_catalog()
            self.catalog_selector.setCurrentIndex(self.catalog_selector.findData(manifest['id']))
        except Exception as exc:self.error(str(exc))

    def install_manifest(self, identity, setup=False, activate=False):
        from .sources import Sources
        from .adapters import get_adapter
        manifest=self.registry.entries[identity]
        adapter=get_adapter(manifest['runtime']['recommended']);runtime=Runtime(self.store,adapter)
        if not adapter.implemented:self.statusBar().showMessage(tr('This runtime is planned, but not available yet.'));return
        if self.runtime_busy:self.statusBar().showMessage(tr('A runtime operation is in progress.'));return
        source=manifest['source'];value=source.get('repo') if source['type']=='huggingface' else source.get('url') or source.get('path')
        if source['type']=='github' and not value:value='https://github.com/'+source['repo']+'/releases/latest'
        def download(metadata):
            if metadata.get('source')=='local':self.show_local_import(metadata,manifest);return
            roles=self.registry.select_files(manifest,metadata)
            self.queue_download('model',manifest['name'],{'metadata':metadata,'filenames':list(roles.values()),'roles':roles,'manifest':manifest,'setup':setup,'activate':activate})
        def resolve_source(_=None):
            receipts=[r for r in self.models.installed() if r.get('valid') and r.get('repo_id')==source.get('repo')]
            if receipts:
                # Reuse only a complete file-role set from one pinned revision.
                for revision in sorted({r['revision'] for r in receipts},reverse=True):
                    candidates=[r for r in receipts if r['revision']==revision]
                    metadata={'repo_id':source.get('repo'),'revision':revision,'files':candidates}
                    try:roles=self.registry.select_files(manifest,metadata)
                    except ValueError:continue
                    selected=[r for r in candidates if r['filename'] in roles.values()]
                    self.offer_imported_profile(selected,{'metadata':metadata,'roles':roles,'manifest':manifest,'setup':setup,'activate':activate});return
            self.jobs.submit('Resolve source',lambda c,p:Sources(self.models).resolve(value,c),download,self.error)
        if runtime.executable.exists():resolve_source()
        else:
            self.jobs.submit('Check for updates',runtime.check,
                lambda release:self.queue_download('runtime',adapter.name,{'adapter_id':adapter.id,'release':release,'install':True},resolve_source),self.error)

    def import_local(self, directory=False):
        filename=QFileDialog.getExistingDirectory(self,tr('Local directory'),str(self.store.models)) if directory else QFileDialog.getOpenFileName(self,tr('Local file'),str(self.store.models),'All files (*)')[0]
        if filename:
            from .registry import inspect_local
            self.jobs.submit('Inspect local model',lambda c,p:inspect_local(filename),self.show_local_import,self.error)

    def show_local_import(self,metadata,manifest=None):
        if manifest is None:
            matches=self.registry.match(metadata)
            if len(matches)==1:manifest=matches[0]
        rows=self.registry.compatibility(metadata);runtime=next((r['id'] for r in rows if r['recommended']), '')
        profile=Profile('model-'+uuid.uuid4().hex[:8],Path(metadata['path']).stem,
            type=manifest['task'] if manifest else (metadata.get('task') or 'asr'),model_path=self.store.relative(Path(metadata['path'])),
            runtime_id=manifest['runtime']['recommended'] if manifest else runtime, requires_mmproj=False,
            architecture=metadata.get('architecture',''), runtime_options=manifest['runtime'].get('options',{}) if manifest else {})
        dialog=ProfileDialog(self.store,profile,self)
        dialog.content_layout.insertWidget(0,label(self.compatibility_text(metadata),'subtitle'))
        dialog.setWindowTitle(tr('Model profile')+' · '+metadata.get('format','')+' · '+metadata.get('quantization','')+' · '+size(metadata['size']))
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.store.put_profile(dialog.profile);self.refresh_profiles(dialog.profile.id);self.refresh_installed()

    def offer_imported_profile(self,receipts,payload):
        self.refresh_installed()
        mains=[r for r in receipts if not r['is_mmproj']]
        if not mains:return
        manifest=payload.get('manifest')
        if not manifest:
            import fnmatch
            matches=[m for m in self.registry.match(payload['metadata']) if fnmatch.fnmatch(mains[0]['filename'].lower(),m['files']['model']['pattern'].lower())]
            manifest=matches[0] if len(matches)==1 else None
        runtime=manifest['runtime']['recommended'] if manifest else next((r['id'] for r in self.registry.compatibility(payload['metadata']) if r['recommended']), '')
        identity=manifest['id'] if manifest else 'model-'+uuid.uuid4().hex[:8]
        if any(p.id==identity for p in self.store.profiles):
            self.refresh_profiles(identity)
            self.nav.setCurrentRow(0)
            if payload.get('setup') or payload.get('activate'):self.service('switch',identity,self.setup_ready if payload.get('setup') else None)
            return
        role_paths={role:next(r['path'] for r in receipts if r['filename']==name) for role,name in payload.get('roles',{}).items()}
        mmproj=role_paths.get('mmproj') or next((r['path'] for r in receipts if r['is_mmproj']), '')
        profile=Profile(identity,manifest['name'] if manifest else Path(mains[0]['filename']).stem,
            type=manifest['task'] if manifest else (payload['metadata'].get('task') or 'asr'),runtime_id=runtime,
            model_path=role_paths.get('model',mains[0]['path']),mmproj_path=mmproj,requires_mmproj=bool(mmproj),
            model_files=role_paths,manifest_id=manifest['id'] if manifest else '',
            runtime_options=manifest['runtime'].get('options',{}) if manifest else {})
        previous=next((p for p in self.store.profiles if p.id==self.store.settings.get('active_profile') and p.type==profile.type),None)
        if manifest and previous:
            profile.host,profile.port=previous.host,previous.port
            profile.compatibility_proxy,profile.proxy_port=previous.compatibility_proxy,previous.proxy_port
        if not manifest:
            dialog=ProfileDialog(self.store,profile,self)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            profile=dialog.profile
        self.store.put_profile(profile);self.refresh_profiles(profile.id)
        self.nav.setCurrentRow(0)
        if payload.get('setup') or payload.get('activate'):self.service('switch',profile.id,self.setup_ready if payload.get('setup') else None)

    def choose_new_task_proxy(self):
        value=self.task_proxy.currentData()
        if value!='custom':self.download_policy={'mode':value};return
        from .network_ui import ProxyDialog
        dialog=ProxyDialog(self.store,self.download_policy,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.download_policy=dialog.value
        else:self.task_proxy.setCurrentIndex(0)

    def edit_download_proxy(self):
        from .network_ui import ProxyDialog
        row=self.download_table.currentRow()
        if row<0:return
        record=self.downloads.records[row]
        if record['state'] in {'Running','Queued','Pausing'}:self.error('Pause the task before changing its proxy.');return
        dialog=ProxyDialog(self.store,record.get('proxy',{'mode':'global'}),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            record['proxy']=dialog.value;self.downloads.save()

    def select_runtime(self):
        from .adapters import get_adapter
        self.runtime=Runtime(self.store,get_adapter(self.runtime_selector.currentData()))
        self.runtime_latest=read_json(self.runtime.receipt('latest'),{})
        self.refresh_runtime()

    def refresh_installed(self):
        records=self.models.installed()
        known={str(self.store.path(r['path'])) for r in records}
        for profile in self.store.profiles:
            path=self.store.path(profile.model_path)
            if not profile.model_path or str(path) in known:continue
            known.add(str(path))
            records.append({'filename':path.name,'path':profile.model_path,'size':path.stat().st_size if path.is_file() else None,
                            'revision':'local','valid':path.exists()})
        self.installed_table.setRowCount(len(records))
        self.models_empty.setVisible(not records)
        updates={(u["record"]["path"]):u["status"] for u in self.model_updates}
        for row,record in enumerate(records):
            values=[record["filename"],size(record["size"]),record["revision"][:12],tr(updates.get(record["path"],"Installed") if record["valid"] else "Missing / incomplete")]
            for col,value in enumerate(values):self.installed_table.setItem(row,col,QTableWidgetItem(value))

    def check_model_updates(self,auto=False):
        def complete(results):
            self.mark_checked("models"); self.model_updates=results; self.refresh_installed()
            count=sum(r["status"]=="Update available" for r in results)
            bind(self.model_update_label,"Check complete · {count} files can be updated",count=count)
            if auto and count and self.store.settings["models_auto_update"]:self.update_models()
        self.jobs.submit("Check model updates",self.models.check_updates,complete,self.background_error if auto else self.error)

    def update_models(self):
        candidates=[r for r in self.model_updates if r["status"]=="Update available"]
        if not candidates:self.statusBar().showMessage(tr("No confirmed model updates. Check for updates first.")); return
        if self.model_update_busy:return
        for repo in sorted({r["record"]["repo_id"] for r in candidates}):
            records=[r for r in candidates if r["record"]["repo_id"]==repo]; metadata=records[0]["metadata"]
            names={r["record"]["filename"] for r in records}
            for filename in list(names):
                matched=match_mmproj(filename,[f["filename"] for f in metadata["files"]])
                if matched:names.add(matched)
            old=[r for r in self.models.installed() if r["repo_id"]==repo and r["filename"] in names]
            self.queue_download("model","Apply model updates · "+repo,{"metadata":metadata,"filenames":sorted(names),"replace":old})

    def build_downloads(self):
        self.download_policy={'mode':'global'}
        self.task_proxy=QComboBox()
        for title,value in [('Use global proxy','global'),('Direct','direct'),('Custom proxy','custom')]:self.task_proxy.addItem(tr(title),value)
        self.task_proxy.currentIndexChanged.connect(self.choose_new_task_proxy)
        self.pages['Downloads'].addWidget(label('Proxy for new downloads','subtitle'))
        self.pages['Downloads'].addWidget(self.task_proxy)
        empty=self.card("Downloads"); self.downloads_empty=empty.parentWidget(); self.downloads_empty.setMinimumHeight(210)
        empty.addStretch(); empty.addWidget(label("No downloads yet","section"))
        empty.addWidget(label("Choose a model or runtime to start your first download.","subtitle"))
        empty.addLayout(buttons(("Model library",lambda:self.nav.setCurrentRow(1)),("Runtime",lambda:self.nav.setCurrentRow(3)))); empty.addStretch()
        self.download_table=table(["Task / File","State","Progress","Downloaded","Speed","ETA / Detail"])
        self.download_table.setMinimumHeight(360); self.pages["Downloads"].addWidget(self.download_table)
        self.download_toolbar=QWidget(); self.download_toolbar.setLayout(buttons(("Pause",lambda:self.download_action("pause")),("Resume / Retry",lambda:self.download_action("resume")),("Cancel",lambda:self.download_action("cancel")),("Download proxy",self.edit_download_proxy)))
        self.download_toolbar.layout().setContentsMargins(0,0,0,0); self.pages["Downloads"].addWidget(self.download_toolbar)
        self.pages["Downloads"].addWidget(label("Resumable downloads. Unfinished tasks can be continued after restarting the app.","subtitle"))
        self.pages["Downloads"].addStretch()

    def queue_download(self,kind,title,payload,done=None):
        record=self.downloads.add(kind,title,payload)
        if 'proxy' not in record:record['proxy']=dict(self.download_policy);self.downloads.save()
        if done:self.download_callbacks[record["id"]]=done
        self.run_download(record); self.nav.setCurrentRow(2)

    def run_download(self,record):
        old=self.download_jobs.get(record["id"])
        if old and self.jobs.items[old]["state"] in {"Running","Pausing"}:return
        kind=record["kind"]; payload=record["payload"]
        if kind=="runtime" and self.runtime_busy:return
        if kind=="runtime":self.runtime_busy=True
        self.downloads.update(record["id"],{"state":"Running","error":""})
        def work(control,progress):
            control.network=record.get('proxy',{'mode':'global'})
            runtime=Runtime(self.store, __import__('lmm.adapters',fromlist=['get_adapter']).get_adapter(payload.get('adapter_id','llama_cpp')))
            if kind=="runtime":
                stage=runtime.stage(payload["release"],control,progress)
                if payload.get("install"):
                    with self.manager.lock:return runtime.install(stage,control,lambda:self.manager.stop_runtime(runtime.adapter.id),self.manager.start_many,self.manager.wait_ready_many)
                return str(stage)
            if kind=="model":
                result=self.models.download(payload["metadata"],payload["filenames"],control,progress)
                if payload.get("replace"):
                    with self.manager.lock:self.models.apply_profile_paths(payload["replace"],result,self.manager)
                return result
            if kind=="app":return updater.stage(self.store,payload,control,progress)
            raise ValueError("Unknown download task.")
        def complete(result):
            if kind=="runtime":self.runtime_busy=False; self.refresh_runtime()
            self.downloads.update(record["id"],{"state":"Completed"}); self.refresh_downloads()
            if kind=="model" and not payload.get("replace"):self.offer_imported_profile(result,payload)
            if kind=="model" and payload.get("replace"):self.check_model_updates()
            if kind=="app":self.refresh_app_update()
            callback=self.download_callbacks.pop(record["id"],None)
            if callback:callback(result)
        def failed(message):
            if kind=="runtime":self.runtime_busy=False
            self.downloads.update(record["id"],{"state":"Failed","error":message}); self.refresh_downloads(); self.error(message)
        self.download_jobs[record["id"]]=self.jobs.submit(record["title"],work,complete,failed,resumable=True)
        self.refresh_downloads()

    def download_action(self,verb):
        row=self.download_table.currentRow()
        if row<0:return
        record=self.downloads.records[row]; key=self.download_jobs.get(record["id"])
        if verb=="resume":
            if record["state"] in {"Paused","Failed","Cancelled"}:self.run_download(record)
        elif key:
            getattr(self.jobs,verb)(key)
        elif verb=="cancel":self.downloads.update(record["id"],{"state":"Cancelled"})
        self.refresh_downloads()

    def refresh_downloads(self):
        self.download_table.setRowCount(len(self.downloads.records))
        self.downloads_empty.setVisible(not self.downloads.records)
        self.download_table.setVisible(bool(self.downloads.records)); self.download_toolbar.setVisible(bool(self.downloads.records))
        for row,record in enumerate(self.downloads.records):
            key=self.download_jobs.get(record["id"])
            if key:
                item=self.jobs.items[key]
                update={k:v for k,v in item.items() if k in {"state","downloaded","total","speed","eta","file","detail","error"}}
                if any(record.get(k)!=v for k,v in update.items()):self.downloads.update(record["id"],update)
                if record["kind"]=="runtime" and item["state"] in {"Paused","Cancelled","Failed","Completed"}:self.runtime_busy=False
            total=record.get("total",0); downloaded=record.get("downloaded",0); eta=record.get("eta")
            progress=f"{downloaded/total*100:.1f}%" if total else "—"
            values=[record.get("file",tr(record["title"])),tr(record["state"]),progress,f"{size(downloaded)} / {size(total)}",size(record.get("speed",0))+"/s",tr(record.get("error") or record.get("detail") or (f"{eta:.0f}s" if eta else "—"))]
            for col,value in enumerate(values):self.download_table.setItem(row,col,QTableWidgetItem(value))
        self.model_update_busy=any(r["kind"]=="model" and r["payload"].get("replace") and r["state"] in {"Running","Pausing"} for r in self.downloads.records)

    def build_runtime(self):
        from .adapters import adapters
        self.runtime_selector=QComboBox()
        for adapter in adapters().values():self.runtime_selector.addItem(adapter.name + ('' if adapter.implemented else ' · '+tr('Reserved')),adapter.id)
        self.pages['Runtime'].addWidget(self.runtime_selector)
        self.runtime_selector.currentIndexChanged.connect(self.select_runtime)
        box=self.card("Runtime"); box.addWidget(label("Engine information","section")); self.runtime_label=label(); box.addWidget(self.runtime_label)
        row=buttons(("Check for updates",self.check_runtime),("Download / Update",self.install_runtime),("Install downloaded version",self.install_staged_runtime))
        self.runtime_buttons=[row.itemAt(i).widget() for i in range(3)];box.addLayout(row)
        self.pages["Runtime"].addWidget(label("The CUDA runtime is managed independently. Updates back up the engine, restart managed services, and roll back if health checks fail.","subtitle"))
        self.pages["Runtime"].addWidget(label("Runtime diagnostics","section"))
        self.runtime_details=QPlainTextEdit(); self.runtime_details.setReadOnly(True); self.runtime_details.setMinimumHeight(240); self.pages["Runtime"].addWidget(self.runtime_details)
        self.pages["Runtime"].addStretch()

    def refresh_runtime(self):
        implemented=self.runtime.adapter.implemented
        for index,button in enumerate(self.runtime_buttons):
            button.setEnabled(implemented and not self.runtime_busy and (index!=2 or self.runtime.receipt('staged').exists()))
        if not implemented:
            self.runtime_label.setText(self.runtime.adapter.name+' · '+tr('Reserved'))
            self.runtime_details.setPlainText(tr('This runtime is planned, but not available yet.'))
            return
        installed=self.runtime.installed(); latest=self.runtime_latest
        present=self.runtime.executable.exists()
        text=tr("Installed: {binary}   ({release})\nLatest: {latest}\nBackend: {backend}",binary=installed.get("binary_tag","—"),release=installed.get("release_tag","—"),latest=latest.get("binary_tag",tr("Not checked")),backend=installed.get("backend",tr("CUDA not installed")))
        if not present:text=self.runtime.adapter.name+" · "+tr("Not installed")+"\n"+text
        elif latest:text+="\n"+tr("Status: {status}",status=tr("Up to date" if latest.get("binary_tag")==installed.get("binary_tag") else "Update available"))
        self.runtime_label.setText(text)
        self.runtime_details.setPlainText(installed.get("version","")+"\n"+installed.get("devices","")+"\n"+str(self.runtime.directory))

    def check_runtime(self,auto=False,done=None):
        runtime=self.runtime
        if not runtime.adapter.implemented:return
        def complete(release):
            self.mark_checked("runtime")
            if self.runtime.adapter.id==runtime.adapter.id:self.runtime_latest=release;self.refresh_runtime()
            if done:done(release)
            elif auto and self.store.settings["runtime_download"] and release["binary_tag"]!=runtime.installed().get("binary_tag"):
                self.queue_download("runtime",runtime.adapter.name,{"adapter_id":runtime.adapter.id,"release":release,"install":self.store.settings["runtime_install"]})
        self.jobs.submit("Check for updates",runtime.check,complete,self.background_error if auto else self.error)

    def install_runtime(self,done=None):
        if not self.runtime.adapter.implemented:return
        if self.runtime_busy:self.statusBar().showMessage(tr("A runtime operation is in progress.")); return
        runtime=self.runtime
        self.check_runtime(done=lambda release:self.queue_download("runtime",runtime.adapter.name,{"adapter_id":runtime.adapter.id,"release":release,"install":True},done))

    def install_staged_runtime(self):
        runtime=self.runtime
        if not runtime.adapter.implemented:return
        staged=read_json(self.runtime.receipt("staged"),{})
        if not staged:self.error("No verified runtime is ready to install."); return
        if self.runtime_busy:return
        self.runtime_busy=True
        def install(control,progress):
            with self.manager.lock:return runtime.install(Path(staged["path"]),control,lambda:self.manager.stop_runtime(runtime.adapter.id),self.manager.start_many,self.manager.wait_ready_many)
        def complete(_):self.runtime_busy=False; self.refresh_runtime()
        def failed(message):self.runtime_busy=False; self.error(message)
        self.jobs.submit("Install downloaded runtime",install,complete,failed)

    def setup_qwen(self):
        self.install_manifest('qwen3-asr-17b-q8',setup=True)

    def setup_ready(self,value):
        atomic_json(self.store.config/"setup_result.json",{"state":"READY","api":value,"gpu":self.gpu_state,"time":datetime.now(timezone.utc).isoformat()})
        self.nav.setCurrentRow(4); self.statusBar().showMessage(tr("Qwen3 ASR is ready for a microphone test"))

    def build_integration(self):
        box=self.card("OpenTypeless"); box.addWidget(label("OpenTypeless connection","section")); self.integration_text=label(); box.addWidget(self.integration_text)
        box.addLayout(buttons(("Copy Base URL",self.copy_base),("Copy Model ID",self.copy_model),("Copy configuration",self.copy_config)))
        self.pages["OpenTypeless"].addWidget(label("Speech test","section"))
        self.mic_combo=QComboBox(); self.pages["OpenTypeless"].addWidget(self.mic_combo); self.refresh_microphones()
        self.pages["OpenTypeless"].addLayout(buttons(("Test microphone",self.start_recording),("Stop and transcribe",self.stop_recording),("Choose audio file",self.select_audio),("Refresh microphones",self.refresh_microphones)))
        self.record_label=label("Audio is saved as mono 16 kHz PCM WAV.","subtitle"); self.pages["OpenTypeless"].addWidget(self.record_label)
        self.transcript=QPlainTextEdit(); self.transcript.setReadOnly(True); bind(self.transcript,"Your transcript will appear here…",setter="setPlaceholderText"); self.transcript.setMinimumHeight(130); self.pages["OpenTypeless"].addWidget(self.transcript)
        self.asr_metrics=label(); self.pages["OpenTypeless"].addWidget(self.asr_metrics)
        toggle=bind(QPushButton(),"Raw response"); toggle.setCheckable(True); self.pages["OpenTypeless"].addWidget(toggle)
        self.raw_response=QPlainTextEdit(); self.raw_response.setReadOnly(True); self.raw_response.hide(); toggle.toggled.connect(self.raw_response.setVisible); self.pages["OpenTypeless"].addWidget(self.raw_response)
        self.pages["OpenTypeless"].addStretch()

    def copy_config(self):
        profile=self.current_profile()
        if profile and self.profile_states.get(profile.id,{}).get("state")=="READY":QApplication.clipboard().setText(self.integration_text.text())
        else:self.error("Wait for the ASR service to be ready.")

    def refresh_microphones(self):
        from PySide6.QtMultimedia import QMediaDevices
        self.mic_combo.clear(); self.mic_combo.addItem(tr("Windows default microphone"),None)
        for device in QMediaDevices.audioInputs():self.mic_combo.addItem(device.description(),device)

    def start_recording(self):
        profile=self.current_profile()
        if not profile or self.profile_states.get(profile.id,{}).get("state")!="READY":self.error("Start the ASR service and wait until it is ready."); return
        try:
            self.recorder.start(self.mic_combo.currentData()); self.record_profile=profile.id
            self.record_started=time.monotonic(); self.clock_timer.start(); self.record_clock()
        except Exception as exc:self.error(exc)

    def record_clock(self):
        if self.record_started is not None:bind(self.record_label,"● Recording…  {seconds:05.1f}s  ·  Maximum 5 minutes",seconds=time.monotonic()-self.record_started)

    def stop_recording(self):
        if not self.recorder.source:return
        raw=self.recorder.stop(); self.clock_timer.stop(); self.record_started=None
        path=self.store.root/"downloads"/"recordings"/(datetime.now().strftime("%Y%m%d-%H%M%S")+".wav")
        identity=self.record_profile; bind(self.record_label,"Saving and transcribing…")
        def work(control,progress):
            info=write_wav(*raw,path)
            if info["silence"]:return {"silence":True,"recording":info}
            result=api.transcribe(self.store.get_profile(identity),path,control,progress)
            return result|{"recording":info,"source":"microphone"}
        self.jobs.submit("Microphone ASR test",work,self.asr_complete,self.error)

    def select_audio(self):
        profile=self.current_profile()
        if not profile:self.error("Select an ASR profile."); return
        filename,_=QFileDialog.getOpenFileName(self,tr("Test audio"),str(self.store.root),tr("Audio (*.wav *.mp3 *.flac *.m4a *.ogg)"))
        if filename:self.jobs.submit("Audio ASR test",lambda c,p:api.transcribe(profile,Path(filename),c,p),self.asr_complete,self.error)

    def asr_complete(self,result):
        if result.get("silence"):
            bind(self.record_label,"Recording is almost silent. Check your Windows input device and microphone permissions."); return
        self.transcript.setPlainText(result["transcript"]); self.raw_response.setPlainText(result["raw"])
        duration=result.get("audio_duration"); rtf=result.get("rtf")
        if duration:bind(self.asr_metrics,"Audio: {duration:.2f}s  ·  Request: {milliseconds:.0f} ms  ·  RTF: {rtf:.3f}",duration=duration,milliseconds=result["request_seconds"]*1000,rtf=rtf)
        else:bind(self.asr_metrics,"Request: {milliseconds:.0f} ms",milliseconds=result["request_seconds"]*1000)
        bind(self.record_label,"Transcribed · WAV saved in downloads/recordings")
        atomic_json(self.store.config/"last_asr_result.json",result|{"gpu":self.gpu_state,"time":datetime.now(timezone.utc).isoformat()})
        if result["transcript"].startswith("language ") and "<asr_text>" in result["transcript"]:
            bind(self.record_label,"Qwen prefix detected. Stop the service and enable Compatibility Proxy in Edit profile → Advanced, then restart.")

    def build_logs(self):
        self.log_source=QComboBox(); self.pages["Logs"].addWidget(self.log_source)
        self.log_source.currentIndexChanged.connect(self.log_source_changed)
        self.pages["Logs"].addLayout(buttons(("Pause / Resume",self.pause_logs),("Clear view",self.clear_logs),("Copy",lambda:QApplication.clipboard().setText(self.log_text.toPlainText())),("Open log folder",lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.logs))))))
        self.log_text=QPlainTextEdit(); self.log_text.setReadOnly(True); self.log_text.setMinimumHeight(480); self.log_text.document().setMaximumBlockCount(2500); self.pages["Logs"].addWidget(self.log_text)

    def log_source_changed(self,*_):
        self.log_offsets={}
        if hasattr(self,"log_text"):self.log_text.clear()

    def pause_logs(self):self.logs_paused=not self.logs_paused; self.statusBar().showMessage(tr("Log display paused" if self.logs_paused else "Log display resumed"))

    def clear_logs(self):
        self.log_text.clear()
        # Keep current offsets. Existing disk logs are neither deleted nor reloaded.

    def read_logs(self,source,offsets):
        paths=[self.store.logs/"app.log"]+[self.store.logs/(p.id+".log") for p in self.store.profiles] if source=="all" else [self.store.logs/(source+".log")]
        chunks=[]; updated=dict(offsets)
        for path in paths:
            if not path.exists():continue
            length=path.stat().st_size; key=str(path); offset=offsets.get(key,max(0,length-64*1024))
            if offset>length:offset=0
            with path.open("rb") as handle:
                handle.seek(max(offset,length-128*1024)); data=handle.read(128*1024); updated[key]=handle.tell()
            if data:chunks.append(("["+path.stem+"]\n" if source=="all" else "")+data.decode("utf-8",errors="replace"))
        return {"source":source,"offsets":updated,"text":"\n".join(chunks)}

    def extend_settings(self):
        from .network_ui import add_network_tab
        add_network_tab(self)
        self.hf_token=QLineEdit(); self.hf_token.setEchoMode(QLineEdit.EchoMode.Password); bind(self.hf_token,"Leave empty to keep the saved token. Encrypted with Windows DPAPI.",setter="setPlaceholderText")
        self.access_settings_box.addWidget(label("Access token (optional)","subtitle")); self.access_settings_box.addWidget(self.hf_token)
        self.clear_token=bind(QCheckBox(),"Remove saved token"); self.access_settings_box.addWidget(self.clear_token)
        self.app_update_label=label(name="subtitle"); self.app_settings_box.addWidget(self.app_update_label)
        self.app_settings_box.addLayout(buttons(("Check for updates",self.check_app_update),("Download app update",self.download_app_update),("Install and restart",self.install_app_update)))
        self.refresh_app_update()

    def settings_guard(self,updated):
        if hasattr(self,'network_editor'):updated['download_proxy']=self.network_editor.policy()
        if updated["default_port"]<1:raise ValueError("Default port must be at least 1.")
        changed_dirs=[k for k in ("models_dir","runtime_dir","logs_dir") if updated[k]!=self.store.settings[k]]
        if changed_dirs and (self.runtime_busy or self.model_update_busy or any(s.get("state") in {"READY","RUNNING","STARTING","LOADING MODEL"} for s in self.profile_states.values()) or any(i["state"] in {"Running","Pausing"} and i["resumable"] for i in self.jobs.items.values())):
            raise ValueError("Stop model services and downloads before changing folders.")
        # Validate writable directory choices without moving existing user data.
        for key in ("models_dir","runtime_dir","logs_dir"):self.store.path(updated[key]).mkdir(parents=True,exist_ok=True)
        if updated["start_with_windows"]!=self.store.settings["start_with_windows"] or updated["start_with_windows"]:set_autostart(updated["start_with_windows"],self.store.root)
        if self.clear_token.isChecked():self.tokens.set(""); self.clear_token.setChecked(False)
        elif self.hf_token.text():self.tokens.set(self.hf_token.text().strip())
        self.hf_token.clear()

    def check_app_update(self,auto=False):
        def complete(result):
            self.mark_checked("app"); self.app_latest=result; atomic_json(self.store.config/"app_latest.json",result); self.refresh_app_update()
        settings=self.store.settings
        self.jobs.submit("Check for updates",lambda c,p:updater.check(settings["app_update_provider"],settings["app_update_url"],c),complete,self.background_error if auto else self.error)

    def refresh_app_update(self):
        text=tr(self.app_latest.get("status","App update source not configured" if not self.store.settings["app_update_url"] else "Not checked"))
        if self.app_latest.get("version"):text+=" · "+tr("Installed {current} · Latest {latest}",current=__version__,latest=self.app_latest["version"])
        staged=read_json(self.store.config/"app_staged.json",{})
        if staged:text+="\n"+tr("Update verified and ready to install.")
        if self.app_latest.get("notes"):text+="\n"+self.app_latest["notes"][:2000]
        self.app_update_label.setText(text)

    def download_app_update(self):
        if not self.app_latest.get("available"):self.error("Configure an update source and check for a new version first."); return
        self.queue_download("app","Download app update",self.app_latest)

    def install_app_update(self):
        staged=read_json(self.store.config/"app_staged.json",{})
        if not staged:self.error("Download and verify the app update first."); return
        if any(i["state"] in {"Running","Pausing"} for i in self.jobs.items.values()):self.error("Wait for other background tasks before installing the app update."); return
        if QMessageBox.question(self,"Install app update","The app will restart. Managed models will stop and restart after the update. Continue?")!=QMessageBox.StandardButton.Yes:return
        def work(control,progress):
            running=self.manager.stop_all()
            try:return updater.prepare_helper(self.store,staged["path"],running)
            except Exception:
                self.manager.start_many(running); raise
        self.jobs.submit("Preparing app update",work,lambda _:self.tray.finish(),self.error)

    def mark_checked(self,kind):
        self.store.settings["last_checks"][kind]=time.time(); self.store.save()

    def daily_checks(self):
        now=time.time(); settings=self.store.settings
        for kind,function in [("runtime",self.check_runtime),("models",self.check_model_updates),("app",self.check_app_update)]:
            if settings[kind+"_check"] and now-settings["last_checks"].get(kind,0)>=86400:
                self.mark_checked(kind); function(auto=True)

    def background_error(self,message):
        logging.getLogger("lmm").warning("Background task: %s",message); self.statusBar().showMessage(tr(message),20000)

    def tick(self):
        self.tick_count+=1
        self.poller.request("gpu",self.monitor.sample)
        profiles=list(self.store.profiles)
        def states():
            result={}
            for profile in profiles:
                state=self.manager.state(profile.id)
                if state["state"]=="RUNNING":state.update(api.snapshot(profile))
                result[profile.id]=state
            return result
        if self.tick_count%2==1:self.poller.request("profiles",states)
        if self.nav.currentRow()==5 and not self.logs_paused:
            source=self.log_source.currentData() or "all"; offsets=dict(self.log_offsets)
            self.poller.request("logs",lambda:self.read_logs(source,offsets))
        self.refresh_downloads()
        if self.tick_count%3600==0:self.daily_checks()

    def polled(self,kind,value):
        if kind=="gpu":
            self.gpu_state=value
            if value.get("available"):
                bind(self.gpu_label,value["name"])
                used=value.get("used"); total=value.get("total")
                if used is not None and total:self.vram_bar.setValue(round(used/total*100)); bind(self.vram_label,"{used} / {total}",used=size(used),total=size(total))
                power=value.get("power")
                bind(self.gpu_detail,"Load  {load}%    ·    {temperature} °C\nPower  {power} W",load=value.get("load") if value.get("load") is not None else "—",temperature=value.get("temperature") if value.get("temperature") is not None else "—",power=f"{power:.1f}" if power is not None else "—")
            else:bind(self.gpu_label,"GPU unavailable"); bind(self.gpu_detail,value.get("error","")); self.vram_bar.setValue(0); bind(self.vram_label,"—")
        elif kind=="profiles":
            if "error" not in value:self.profile_states.update(value); self.render_state()
        elif kind=="logs" and not self.logs_paused and value.get("source")==self.log_source.currentData():
            self.log_offsets=value["offsets"]
            if value["text"]:self.log_text.appendPlainText(value["text"].rstrip())

    def shutdown(self):
        self.timer.stop(); self.clock_timer.stop()
        if self.recorder.source:self.recorder.stop()
        for item in self.jobs.items.values():item["control"].event.set()
        self.poller.close(); self.jobs.pool.shutdown(wait=False,cancel_futures=True)

    def external_action(self,message):
        action=message.get("action","show")
        self.tray.show_window()
        if action=='switch-model':
            identity=message.get('id','')
            index=self.profile_combo.findData(identity)
            if index<0:index=self.profile_combo.findData('catalog:'+identity)
            if index<0:self.error('Create a profile first.');return
            self.nav.setCurrentRow(0);self.profile_combo.setCurrentIndex(index);self.use_selected_model()
        elif action=="setup":self.setup_qwen()
        elif action=="record":
            duration=max(1,min(300,float(message.get("seconds",10))))
            self.nav.setCurrentRow(4); self.start_recording()
            if self.recorder.source:QTimer.singleShot(round(duration*1000),self.stop_recording)
        elif action=="test-audio":
            profile=self.current_profile(); audio=Path(message.get("path",""))
            if profile and audio.is_file():self.jobs.submit("Audio ASR test",lambda c,p:api.transcribe(profile,audio,c,p),self.asr_complete,self.error)
