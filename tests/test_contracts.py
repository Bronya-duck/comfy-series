import copy
import hashlib
import io
import json
import socket
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PIL import Image
from comfy_series import assets, engine, library
from comfy_series.common import Config, Store, SeriesError, digest, read_json, write_json
from comfy_series.ingest import ingest
from comfy_series.web import allowed_file, render
from comfy_series.workflow import normalize_request, build_graph, validate_graph, to_canvas, from_canvas

SCHEMA = read_json(Path(__file__).parent / 'fixtures/node_schema.json')


class LocalFixture(BaseHTTPRequestHandler):
    payload = b'fixture-weight-' * 200_000
    cut = True
    ranges = []
    def log_message(self, *args):
        pass
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Length', str(len(self.payload)))
        self.end_headers()
    def do_GET(self):
        if self.path == '/denied':
            self.send_error(403)
            return
        if self.path == '/page':
            data = b'<h1>Archive requirements</h1><p>Blue steel shelves</p><script>bad instruction</script>'
            self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers()
            self.wfile.write(data)
            return
        offset = int(self.headers.get('Range', 'bytes=0-')[6:].split('-')[0])
        type(self).ranges.append(offset)
        if self.path == '/ignore':
            offset = 0
        self.send_response(206 if offset else 200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(self.payload) - offset))
        if offset:
            self.send_header('Content-Range', f'bytes {offset}-{len(self.payload)-1}/{len(self.payload)}')
        self.end_headers()
        if self.path in ('/cut', '/ignore') and type(self).cut:
            type(self).cut = False
            self.wfile.write(self.payload[:1_300_000]); self.wfile.flush()
            self.connection.shutdown(socket.SHUT_RDWR); self.connection.close()
        else:
            self.wfile.write(self.payload[offset:])


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), LocalFixture)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.http.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = Config(self.temp.name)
        self.config.comfy_root = Path(self.temp.name) / 'external-comfy'
        self.config.poll_seconds = .001
        self.config.timeout_seconds = .002
        self.store = Store(self.config)
        self.style = self.store.create_style({'display_name':'fixture', 'mode':'txt2img',
            'locked_generation_settings':{'checkpoint':'juggernautXL_XI.safetensors',
                'first_pass':{'steps':2}, 'reference_conditioning':[]},
            'prompt_blocks':{'fixed_positive_style':'cold photography'}})
        self.store.create_series(self.style['style_key'], series_id='SC-T', isolated=True)
    def tearDown(self):
        self.store.db.close(); self.temp.cleanup()
    def error(self, code, func, *args, **kwargs):
        with self.assertRaises(SeriesError) as ctx:
            func(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception
    def spec(self, path='/weight', name='fixture.bin', checksum=None):
        return {'category':'ipadapter', 'name':name, 'url':self.url+path,
            'expected_bytes':len(LocalFixture.payload), 'sha256':checksum or hashlib.sha256(LocalFixture.payload).hexdigest(),
            'revision':'fixture-v1', 'source_url':self.url+path}
    def request(self, **kwargs):
        return dict(brief='room', prompt='cold room', style=self.style['style_key'], series_id='SC-T',
                    output={'width':1001,'height':733}, **kwargs)
    def job(self):
        with patch.object(engine, 'bind_assets', return_value=[]):
            return engine.prepare(self.store, self.request())
    def rendered(self, job, number=1):
        folder = Path(job['folder']) / 'image_001' / f'round_{number}'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'result.png'; Image.new('RGB', (1001,733), 'blue').save(path)
        attempt = {'number':number,'status':'rendered','path':str(path), 'folder':str(folder)}
        job['images'][0]['attempts'].append(attempt)
        job['images'][0]['latest_path'] = str(path)
        write_json(folder/'manifest.json', {})
        engine.save_job(self.store, job)
        return attempt

    def test_defaults_and_odd_output(self):
        self.assertEqual(normalize_request({'brief':'room'}, {'defaults':{'output_resolution':[3,2]}})['output'],
            {'width':1824,'height':1248,'count':1,'format':'PNG'})
        req = normalize_request(self.request())
        graph, meta = build_graph(req, self.style, {})
        self.assertEqual(meta['output_size'], [1001,733])
        self.assertTrue(all(x % 8 == 0 for x in meta['generation_size']))
        self.assertLess(abs(meta['generation_size'][0]/meta['generation_size'][1]-1001/733), .02)
        self.assertEqual(meta['save_node'], str(len(graph)))
        req['constraints']['must']=['steel archive crates']
        _, meta=build_graph(req,self.style,{})
        self.assertIn('steel archive crates',meta['positive'])
    def test_conflicting_ratio_and_types(self):
        self.error('dimensions_conflict', normalize_request, {'brief':'room','output':{'width':1001,'height':733,'aspect_ratio':'3:2'}})
        self.error('incomplete_dimensions', normalize_request, {'brief':'room','output':{'width':1001}})
        self.error('invalid_constraints', normalize_request, {'brief':'room','constraints':{'avoid':'people'}})
        self.error('invalid_output', normalize_request, {'brief':'room','output':[]})
        self.error('invalid_seed', normalize_request, {'brief':'room','seed':True})
    def test_graph_roundtrip_and_bad_links(self):
        graph, _ = build_graph(normalize_request(self.request()), self.style, {})
        validate_graph(graph, SCHEMA)
        self.assertEqual(from_canvas(to_canvas(graph, SCHEMA), SCHEMA), graph)
        broken = copy.deepcopy(graph); broken['2']['inputs']['clip']=['1',0]
        ex = self.error('workflow_validation', validate_graph, broken, SCHEMA)
        self.assertIn('type_mismatch', str(ex.details))
        ex = self.error('workflow_validation', validate_graph, graph, {})
        self.assertIn('missing_node', str(ex.details))
    def test_graph_cycle_rejected(self):
        g={'1':{'class_type':'ImageScale','inputs':{'image':['1',0],'width':1001,'height':733,'crop':'center','upscale_method':'lanczos'}}}
        ex=self.error('workflow_validation',validate_graph,g,SCHEMA)
        self.assertIn('cycle', str(ex.details))
    def test_reference_is_versioned_and_roundtrips(self):
        request=normalize_request(self.request(references=[{'material_id':'M-X','role':'style'}]))
        self.error('style_revision_required', build_graph, request, self.style, {})
        style=copy.deepcopy(self.style)
        style['locked_generation_settings']['reference_conditioning']=[{'method':'ipadapter','material_id':'M-X',
            'model':'ip-adapter-plus_sdxl_vit-h.safetensors','clip_vision':'CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors'}]
        info=copy.deepcopy(SCHEMA); info['LoadImage']['input']['required']['image'][0]=['ref.png']
        graph, meta=build_graph(request,style,{'M-X':'ref.png'})
        self.assertEqual(meta['reference_method'],'ipadapter')
        self.assertEqual(from_canvas(to_canvas(graph,info),info),graph)
        self.assertIn('EmptyLatentImage',[x['class_type'] for x in graph.values()])
        self.assertNotIn('VAEEncodeTiled',[x['class_type'] for x in graph.values()])
    def test_series_pins_existing_revision(self):
        self.style['visual_baseline']={'image_path':'old.png'}
        newer=self.store.create_style(dict(self.style,style_id=self.style['style_id']))
        self.assertNotIn('visual_baseline',newer)
        self.assertEqual(newer['revision'],2)
        self.assertEqual(self.store.resolve_style(self.style['style_id'])['style_key'],newer['style_key'])
        raw=self.request();raw['style']='【同风格:S001】'
        with patch.object(engine,'bind_assets',return_value=[]):
            j=engine.prepare(self.store,raw)
        self.assertEqual(j['style_key'],self.style['style_key'])
        self.error('series_style_locked',self.store.create_series,newer['style_key'],series_id='SC-T')
    def test_no_id_reuses_formal_series_and_its_budget(self):
        self.store.create_series(self.style['style_key'],series_id='SC-FORMAL')
        raw=self.request();raw.pop('series_id')
        with patch.object(engine,'bind_assets',return_value=[]):
            j=engine.prepare(self.store,raw)
        self.assertEqual(j['series_id'],'SC-FORMAL')
    def test_delete_switch_requires_completed_matching_plan(self):
        newer=self.store.create_style(dict(self.style,style_id=self.style['style_id']))
        self.store.put('settings','active_style_key',self.style['style_key'])
        self.store.put('cleanup','DEL-T',{'status':'awaiting_human_confirmation','confirmed_ids':[],'human_confirmation':'Human'})
        self.store.create_series(newer['style_key'],series_id='SC-NEW')
        raw=self.request();raw.update(style=newer['style_key'],series_id='SC-NEW')
        with patch.object(engine,'bind_assets',return_value=[]):
            self.error('switch_cleanup_unconfirmed',engine.prepare,self.store,raw,'delete','Human','DEL-T')
    def test_style_switch_requires_human_receipt(self):
        newer=self.store.create_style(dict(self.style,style_id=self.style['style_id']))
        self.store.put('settings','active_style_key',self.style['style_key'])
        self.store.create_series(newer['style_key'],series_id='SC-NEW')
        raw=self.request();raw.update(style=newer['style_key'],series_id='SC-NEW')
        with patch.object(engine,'bind_assets',return_value=[]):
            self.error('switch_decision_required',engine.prepare,self.store,raw)
            self.error('switch_decision_required',engine.prepare,self.store,raw,'keep','')
            j=engine.prepare(self.store,raw,'keep','Human: keep all old weights')
        self.assertEqual(j['style_key'],newer['style_key'])
    def test_interrupted_download_resumes_by_range(self):
        orphan=self.config.model_root/'ipadapter/orphan.bin.part'
        orphan.parent.mkdir(parents=True,exist_ok=True);orphan.write_bytes(b'unknown source')
        self.error('partial_without_provenance',assets.download,self.store,self.spec(name='orphan.bin'),'SC-T',1)
        write_json(orphan.with_name(orphan.name+'.json'),{'fingerprint':'another-source'})
        self.error('partial_source_mismatch',assets.download,self.store,self.spec(name='orphan.bin'),'SC-T',1)
        self.assertEqual(self.store.budget('SC-T')['reserved'],0)
        LocalFixture.cut=True; LocalFixture.ranges=[]
        self.error('download_interrupted',assets.download,self.store,self.spec('/cut'),'SC-T',1)
        self.assertGreater(self.store.budget('SC-T')['reserved'],0)
        result=assets.download(self.store,self.spec('/cut'),'SC-T',1)
        self.assertEqual(digest(result['asset']['path']),self.spec()['sha256'])
        self.assertTrue(any(x>0 for x in LocalFixture.ranges))
        self.assertEqual(self.store.budget('SC-T')['used'],len(LocalFixture.payload))
        self.assertEqual(self.store.budget('SC-T')['reserved'],0)
    def test_server_ignoring_range_restarts(self):
        LocalFixture.cut=True
        self.error('download_interrupted',assets.download,self.store,self.spec('/ignore'),'SC-T',1)
        r=assets.download(self.store,self.spec('/ignore'),'SC-T',1)
        self.assertEqual(Path(r['asset']['path']).read_bytes(),LocalFixture.payload)
    def test_bad_hash_is_not_installed(self):
        self.error('model_hash_mismatch',assets.download,self.store,self.spec(checksum='0'*64),'SC-T',1)
        self.assertFalse((self.config.model_root/'ipadapter/fixture.bin').exists())
        self.assertEqual(self.store.budget('SC-T')['reserved'],0)
    def test_denied_fallback_and_budget_fallback(self):
        candidates=[self.spec('/denied','denied.bin'), self.spec('/weight','good.bin')]
        r=assets.resolve_candidates(self.store,candidates,'SC-T')
        self.assertEqual(r['alternatives_skipped'][0]['code'],'model_source_unavailable')
        series=self.store.need('series','SC-T');series['download_budget_bytes']=len(LocalFixture.payload)
        self.store.put('series','SC-T',series)
        r=assets.resolve_candidates(self.store,[self.spec('/weight','too-big.bin'),self.spec('/weight','good.bin')],'SC-T')
        self.assertEqual(r['alternatives_skipped'][0]['code'],'download_budget')
        self.assertTrue(r['reused'])
    def test_cleanup_confirmation_and_cumulative_budget(self):
        r=assets.download(self.store,self.spec(),'SC-T');aid=r['asset']['id']
        plan=assets.cleanup_plan(self.store,[aid])
        self.error('confirmation_required',assets.cleanup_execute,self.store,plan['id'],[aid],'')
        self.assertTrue(Path(r['asset']['path']).is_file())
        assets.cleanup_execute(self.store,plan['id'],[aid],'Human confirmed fixture deletion')
        self.assertFalse(Path(r['asset']['path']).exists())
        self.assertEqual(self.store.budget('SC-T')['used'],len(LocalFixture.payload))
    def test_cleanup_changed_file_and_unsafe_path(self):
        r=assets.download(self.store,self.spec(),'SC-T');aid=r['asset']['id']
        plan=assets.cleanup_plan(self.store,[aid]);Path(r['asset']['path']).write_bytes(b'changed')
        self.error('model_changed',assets.cleanup_execute,self.store,plan['id'],[aid],'Human confirmed fixture deletion')
        a=r['asset'];a['path']=str(self.config.root/'outside.bin');Path(a['path']).write_bytes(b'outside')
        self.store.put('assets',aid,a)
        self.error('unsafe_model_path',assets.cleanup_plan,self.store,[aid])
    def test_corrupt_safetensors_is_rejected_before_load(self):
        p=self.config.model_root/'checkpoints/broken.safetensors';p.parent.mkdir(parents=True);p.write_bytes(b'\0'*100)
        self.error('model_invalid',assets.find_asset,self.store,'checkpoints',p.name)
        self.assertTrue(p.exists())
    def test_materials_have_source_and_visual_fallback(self):
        p=self.config.root/'requirements.md';p.write_text('Blue steel shelves',encoding='utf-8')
        txt=ingest(self.store,str(p),'context')
        self.assertEqual(Path(txt['text_path']).read_text(),'Blue steel shelves')
        url=ingest(self.store,self.url+'/page')
        self.assertIn('Archive requirements',Path(url['text_path']).read_text())
        self.assertNotIn('bad instruction',Path(url['text_path']).read_text())
        p=self.config.root/'scanned.pdf';doc=pymupdf.open();doc.new_page();doc.new_page().insert_text((20,20),'Requirements');doc.save(p);doc.close()
        pdf=ingest(self.store,str(p),pages=[1])
        self.assertEqual(pdf['needs_visual_reading'],[1]);self.assertEqual(pdf['unrendered_pages'],[2])
        self.assertTrue(Path(pdf['visual_pages'][0]['path']).is_file())
        self.assertIn('Requirements',Path(pdf['text_path']).read_text())
        self.error('invalid_pages',ingest,self.store,str(p),pages=[3])
    def test_docx_text_and_embedded_reference(self):
        p=self.config.root/'brief.docx';png=io.BytesIO();Image.new('RGB',(12,12),'red').save(png,format='PNG')
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:t>Cold archive</w:t></w:document>')
            z.writestr('word/media/reference.png',png.getvalue())
        doc=ingest(self.store,str(p))
        self.assertEqual(Path(doc['text_path']).read_text(),'Cold archive')
        self.assertEqual(len(doc['embedded_images']),1)
    def test_visual_review_requires_actual_output_and_honest_status(self):
        j=self.job();a=self.rendered(j)
        r={'index':0,'round':1,'viewed_path':a['path'],'accepted':True,
            'checks':dict(subject='partial',composition='pass',style='pass',defects='pass')}
        self.error('review_contradiction',engine.review,self.store,j['id'],[r])
        r['checks']['subject']='pass';r['viewed_path']='wrong.png'
        self.error('review_not_viewed',engine.review,self.store,j['id'],[r])
        r['viewed_path']=a['path'];result=engine.review(self.store,j['id'],[r])
        self.assertEqual(result['status'],'accepted')
        self.assertEqual(self.store.need('styles',self.style['style_key'])['visual_baseline']['image_path'],a['path'])
    def test_best_result_survives_worse_retry(self):
        j=self.job();a=self.rendered(j)
        r={'index':0,'round':1,'viewed_path':a['path'],'accepted':False,'checks':dict(subject='partial',composition='pass',style='pass',defects='pass')}
        j=engine.review(self.store,j['id'],[r]);b=self.rendered(j,2)
        r.update(round=2,viewed_path=b['path'],checks=dict(subject='fail',composition='partial',style='pass',defects='partial'))
        j=engine.review(self.store,j['id'],[r]);self.assertEqual(j['images'][0]['best_path'],a['path'])
    def test_oom_stops_at_three_rounds_and_preserves_errors(self):
        j=self.job()
        class Fake:
            def __init__(self,config): self.counter=0
            def info(self): return SCHEMA
            def submit(self,*args): self.counter+=1;return {'prompt_id':str(self.counter)}
            def history(self,prompt): return {'status':{'status_str':'error','messages':[['execution_error',{'exception_type':'OutOfMemoryError'}]]}}
            def free_memory(self): pass
        with patch.object(engine,'ComfyClient',Fake),patch.object(engine,'bind_assets',return_value=[]):
            result=engine.run(self.store,j['id'])
            self.assertEqual(len(result['images'][0]['attempts']),3)
            again=engine.run(self.store,j['id'])
            self.assertEqual(len(again['images'][0]['attempts']),3)
        self.assertEqual(result['status'],'failed')
        self.assertTrue(all(x['error'] for x in result['images'][0]['attempts']))
    def test_pending_resume_never_duplicates_submission(self):
        j=self.job()
        class Fake:
            calls=0
            def __init__(self,c): pass
            def info(self): return SCHEMA
            def submit(self,*args): type(self).calls+=1;return {'prompt_id':'pending-id'}
            def history(self,p): return None
            def queue(self): return {'queue_running':[[0,'pending-id']],'queue_pending':[]}
        with patch.object(engine,'ComfyClient',Fake),patch.object(engine,'bind_assets',return_value=[]):
            self.error('execution_pending',engine.run,self.store,j['id'])
            self.error('execution_pending',engine.run,self.store,j['id'])
        self.assertEqual(Fake.calls,1)
        self.assertEqual(len(self.store.need('jobs',j['id'])['images'][0]['attempts']),1)
    def test_lost_submission_response_is_recovered_without_resubmit(self):
        j=self.job()
        class Fake:
            calls=0
            def __init__(self,c): pass
            def info(self): return SCHEMA
            def submit(self,*args): type(self).calls+=1;raise SeriesError('submission_unknown','lost response')
            def find_submission(self,jid,prefix): return 'recovered-prompt'
            def history(self,p): return None
            def queue(self): return {'queue_running':[[0,'recovered-prompt']],'queue_pending':[]}
        with patch.object(engine,'ComfyClient',Fake),patch.object(engine,'bind_assets',return_value=[]):
            self.error('submission_unknown',engine.run,self.store,j['id'])
            self.error('execution_pending',engine.run,self.store,j['id'])
        self.assertEqual(Fake.calls,1)
        result=self.store.need('jobs',j['id'])
        self.assertEqual(result['images'][0]['attempts'][0]['prompt_id'],'recovered-prompt')
    def test_history_disconnect_preserves_known_prompt(self):
        j=self.job()
        class Fake:
            calls=0
            def __init__(self,c): pass
            def info(self): return SCHEMA
            def submit(self,*args): type(self).calls+=1;return {'prompt_id':'known-prompt'}
            def history(self,p): raise SeriesError('comfy_unavailable','disconnect')
        with patch.object(engine,'ComfyClient',Fake),patch.object(engine,'bind_assets',return_value=[]):
            self.error('comfy_unavailable',engine.run,self.store,j['id'])
            self.error('comfy_unavailable',engine.run,self.store,j['id'])
        self.assertEqual(Fake.calls,1)
        self.assertEqual(self.store.need('jobs',j['id'])['images'][0]['attempts'][0]['status'],'queued')
    def test_gallery_escape_and_path_boundary(self):
        st=self.style;st['display_name']='<script>alert(1)</script>';self.store.put('styles',st['style_key'],st)
        self.assertNotIn('<script>alert(1)</script>',render(self.store))
        self.assertIn('&lt;script&gt;',render(self.store))
        self.assertFalse(allowed_file(self.config,self.config.data/'models/secret.safetensors'))
        self.assertFalse(allowed_file(self.config,self.config.data/'runs/../../outside.txt'))
        self.assertTrue(allowed_file(self.config,self.config.data/'runs/job/workflow.json'))
    def test_library_reimport_preserves_validation_only_for_same_content(self):
        p=self.config.data/'library/workflows/sample.json';write_json(p,{})
        seed=self.config.root/'seed.json';record={'id':'sample','title':'Sample','url':self.url,'cached_path':str(p.relative_to(self.config.root)),'revision':'v1','validation_status':'unverified'}
        write_json(seed,[record]);library.import_library(self.store,seed)
        old=self.store.need('sources','sample');old['validation_status']='schema_validated';self.store.put('sources','sample',old)
        library.import_library(self.store,seed);self.assertEqual(self.store.need('sources','sample')['validation_status'],'schema_validated')
        write_json(p,{'changed':True});library.import_library(self.store,seed)
        self.assertEqual(self.store.need('sources','sample')['validation_status'],'unverified')


if __name__ == '__main__':
    unittest.main(verbosity=2)
