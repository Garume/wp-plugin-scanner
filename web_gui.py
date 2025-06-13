from __future__ import annotations
import json
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from flask import Flask, Response, request, jsonify, render_template

from wp_plugin_scanner.downloader import RequestsDownloader
from wp_plugin_scanner.manager import AuditManager
from wp_plugin_scanner.scanner import UploadScanner
from wp_plugin_scanner.searcher import PluginSearcher
from wp_plugin_scanner.reporter import SQLiteReporter

app = Flask(__name__, template_folder='wp_plugin_scanner/templates')

searcher = PluginSearcher()
db_reporter = SQLiteReporter()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search():
    kw = request.args.get('kw', '')
    try:
        slugs = searcher.search(kw)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'slugs': slugs})

@app.route('/results')
def results():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    total = db_reporter.count()
    rows = db_reporter.fetch_page(page, per_page)
    return render_template('results.html', results=rows, page=page, per_page=per_page, total=total)

class MemoryReporter:
    def __init__(self):
        self.results = []
    def already_done(self, slug: str) -> bool:
        return False
    def add_result(self, result):
        self.results.append(result)

@app.route('/scan')
def scan():
    data = request.args.get('data')
    if not data:
        return 'no data', 400
    opts = json.loads(data)
    slugs = opts.get('slugs', [])
    if not slugs:
        return 'no slugs', 400
    workers = int(opts.get('workers', 8))
    timeout = int(opts.get('timeout', 30))
    retries = int(opts.get('retries', 3))
    save = bool(opts.get('save', True))
    skip = bool(opts.get('skip', True))

    reporter = MemoryReporter()
    mgr = AuditManager(RequestsDownloader(retries=retries, timeout=timeout), UploadScanner(), reporter, save_sources=save, max_workers=workers)

    def event_stream():
        total = len(slugs)
        q: queue.Queue[dict | None] = queue.Queue()

        def worker():
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = []
                for idx, slug in enumerate(slugs, start=1):
                    if skip and reporter.already_done(slug):
                        continue
                    q.put({'type':'progress',
                           'msg':f'Queue {slug}',
                           'count':f'{idx}/{total}',
                           'percent':int(idx/total*100)})
                    futs.append(ex.submit(mgr._process_slug, slug))
                for i, fut in enumerate(as_completed(futs), start=1):
                    res = fut.result()
                    reporter.add_result(res)
                    db_reporter.add_result(res)
                    q.put({'type':'result','slug':res.slug,'time':res.readable_time,'detail':res.status if res.status not in ('True','False','skipped') else '', 'class': 'status-found' if res.status=='True' else 'status-not-found' if res.status=='False' else 'status-error' if res.status.startswith('error') else 'status-scanning', 'label': 'Upload Found' if res.status=='True' else 'Clean' if res.status=='False' else 'Error' if res.status.startswith('error') else res.status})
                    q.put({'type':'progress','msg':f'Finished {res.slug}','count':f'{i}/{total}','percent':int(i/total*100)})
            q.put({'type':'done'})
            q.put(None)
        Thread(target=worker, daemon=True).start()
        while True:
            item = q.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return Response(event_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True)
