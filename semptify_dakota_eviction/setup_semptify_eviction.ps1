# setup_semptify_eviction.ps1
# All-in-one bootstrap for Semptify Eviction Defense (FastAPI + assets + ZIP flow)

$ErrorActionPreference = "Stop"

# 1) Project layout
$root = Join-Path (Get-Location) "Semptify_EvictionDefense"
$dirs = @(
    "$root/app",
    "$root/app/static",
    "$root/app/templates",
    "$root/app/assets/forms",
    "$root/app/assets/help",
    "$root/app/assets/exports",
    "$root/app/assets/evidence"
)
foreach ($d in $dirs) { if (!(Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null } }

# 2) Requirements
@"
fastapi==0.115.2
uvicorn[standard]==0.31.0
python-multipart==0.0.9
jinja2==3.1.4
pydantic==2.9.2
"@ | Set-Content -Path "$root/requirements.txt" -Encoding UTF8

# 3) README
@"
# Semptify Eviction Defense (Dakota County)

- One-click tenant ZIP handoff: Answer/Counterclaim + evidence + language help.
- Quad-lingual UI: English, Spanish, Somali, Arabic.
- Endpoints:
  - GET / -> Web UI
  - GET /forms -> JSON catalog of forms
  - GET /guidefile -> Link to MN Guide & File
  - GET /help?lang=en|es|so|ar -> Short help text
  - POST /zip -> Build ZIP handoff (forms + evidence + help)
  - POST /upload -> Upload evidence (images/docs)
"@ | Set-Content -Path "$root/README.md" -Encoding UTF8

# 4) Forms placeholders (replace with latest official PDFs when ready)
# You can swap URLs with official Minnesota Judicial Branch links.
$forms = @(
    @{ name="Answer_Counterclaim_Form.pdf"; url="https://example.com/Answer_Counterclaim_Form.pdf" },
    @{ name="Affidavit_of_Service.pdf";    url="https://example.com/Affidavit_of_Service.pdf" },
    @{ name="Motion_to_Dismiss.pdf";       url="https://example.com/Motion_to_Dismiss.pdf" }
)
foreach ($f in $forms) {
    $target = Join-Path "$root/app/assets/forms" $f.name
    if (!(Test-Path $target)) {
        # Placeholder file to avoid broken references if offline
        @"
This is a placeholder for $($f.name).
Replace with the official PDF from the Minnesota Judicial Branch.
"@ | Set-Content -Path $target -Encoding UTF8
    }
}

# 5) Quad-lingual help text
@"
List each counterclaim separately. Attach evidence. File via Guide & File or clerk before the hearing. Log in early to Zoom.
"@ | Set-Content -Path "$root/app/assets/help/help_en.txt" -Encoding UTF8
@"
Enumere cada contrademanda por separado. Adjunte pruebas. Presente por Guide & File o en la oficina antes de la audiencia. Inicie sesión temprano en Zoom.
"@ | Set-Content -Path "$root/app/assets/help/help_es.txt" -Encoding UTF8
@"
Sheeg dacwad kasta si gooni ah. Ku lifaaq caddeyn. Gudbi ka hor dhageysiga adigoo isticmaalaya Guide & File ama xafiiska. Ku soo xir Zoom hore.
"@ | Set-Content -Path "$root/app/assets/help/help_so.txt" -Encoding UTF8
@"
اذكر كل دعوى مضادة بشكل منفصل. أرفق الأدلة. قدم عبر Guide & File أو لدى كاتب المحكمة قبل الجلسة. سجّل الدخول مبكرًا إلى Zoom.
"@ | Set-Content -Path "$root/app/assets/help/help_ar.txt" -Encoding UTF8

# 6) Minimal HTML template
@"
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Semptify Eviction Defense</title>
  <style>
    body { font-family: system-ui, Arial; margin: 2rem; line-height:1.5; }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap:1rem; }
    .card { border:1px solid #ddd; border-radius:8px; padding:1rem; }
    button { padding:0.6rem 1rem; }
    label { font-weight:600; }
  </style>
</head>
<body>
  <h1>Semptify Eviction Defense — Dakota County</h1>

  <div class="grid">
    <div class="card">
      <h2>Forms</h2>
      <p>Answer & Counterclaim, Affidavit of Service, and Motion templates.</p>
      <a href="/forms" target="_blank"><button>View forms JSON</button></a>
      <a href="/guidefile" target="_blank"><button>Open Guide & File</button></a>
    </div>
    <div class="card">
      <h2>Help text</h2>
      <label for="lang">Language</label>
      <select id="lang">
        <option value="en">English</option>
        <option value="es">Español</option>
        <option value="so">Somali</option>
        <option value="ar">العربية</option>
      </select>
      <button onclick="loadHelp()">Load</button>
      <pre id="help" style="white-space:pre-wrap;"></pre>
    </div>
    <div class="card">
      <h2>Evidence upload</h2>
      <form id="uploadForm">
        <input type="file" name="file" multiple />
        <button type="submit">Upload</button>
      </form>
      <pre id="uploadStatus"></pre>
    </div>
    <div class="card">
      <h2>Build tenant ZIP</h2>
      <form id="zipForm">
        <label>Tenant name</label><br/>
        <input name="tenant_name" required/><br/>
        <label>Case number</label><br/>
        <input name="case_number" required/><br/>
        <button type="submit">Generate ZIP</button>
      </form>
      <div id="zipLink"></div>
    </div>
  </div>

<script>
async function loadHelp(){
  const lang = document.getElementById('lang').value;
  const res = await fetch('/help?lang=' + lang);
  document.getElementById('help').textContent = await res.text();
}
document.getElementById('uploadForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const form = e.target;
  const data = new FormData(form);
  const res = await fetch('/upload', { method:'POST', body:data });
  document.getElementById('uploadStatus').textContent = await res.text();
});
document.getElementById('zipForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const formData = new FormData(e.target);
  const res = await fetch('/zip', { method:'POST', body: formData });
  if(res.ok){
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'Tenant_ZIP_handoff.zip';
    a.textContent = 'Download ZIP';
    document.getElementById('zipLink').innerHTML = '';
    document.getElementById('zipLink').appendChild(a);
  } else {
    document.getElementById('zipLink').textContent = 'ZIP generation failed';
  }
});
</script>
</body>
</html>
"@ | Set-Content -Path "$root/app/templates/index.html" -Encoding UTF8

# 7) FastAPI app
@"
from fastapi import FastAPI, UploadFile, File, Form, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pathlib import Path
import shutil, zipfile

BASE = Path(__file__).resolve().parent
ASSETS = BASE / 'assets'
FORMS = ASSETS / 'forms'
HELP = ASSETS / 'help'
EXPORTS = ASSETS / 'exports'
EVIDENCE = ASSETS / 'evidence'

app = FastAPI(title='Semptify Eviction Defense')

app.mount('/static', StaticFiles(directory=str(BASE / 'static')), name='static')
templates = Jinja2Templates(directory=str(BASE / 'templates'))

@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse('index.html', { 'request': request })

@app.get('/forms')
def list_forms():
    items = []
    for p in FORMS.iterdir():
        if p.is_file():
            items.append({'name': p.name, 'path': f'/forms/file/{p.name}'})
    return JSONResponse(items)

@app.get('/forms/file/{name}')
def get_form(name: str):
    path = FORMS / name
    if not path.exists():
        return PlainTextResponse('Not found', status_code=404)
    return FileResponse(str(path), filename=name)

@app.get('/guidefile')
def guidefile():
    # Replace with official Guide & File link for Minnesota
    url = 'https://www.mncourts.gov/Help-Topics/Guide-and-File.aspx'
    return JSONResponse({'url': url})

@app.get('/help')
def help_text(lang: str = 'en'):
    map = {
        'en': HELP / 'help_en.txt',
        'es': HELP / 'help_es.txt',
        'so': HELP / 'help_so.txt',
        'ar': HELP / 'help_ar.txt'
    }
    path = map.get(lang, map['en'])
    if not path.exists():
        return PlainTextResponse('Help text missing', status_code=404)
    return PlainTextResponse(path.read_text(encoding='utf-8'))

@app.post('/upload')
async def upload(file: UploadFile = File(...)):
    dest = EVIDENCE / file.filename
    with dest.open('wb') as f:
        shutil.copyfileobj(file.file, f)
    return PlainTextResponse(f'Uploaded: {file.filename}')

@app.post('/zip')
async def build_zip(
    tenant_name: str = Form(...),
    case_number: str = Form(...)
):
    zip_path = EXPORTS / 'Tenant_ZIP_handoff.zip'
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        # Include forms
        for p in FORMS.iterdir():
            if p.is_file():
                z.write(p, arcname=f'forms/{p.name}')
        # Include evidence
        for p in EVIDENCE.iterdir():
            if p.is_file():
                z.write(p, arcname=f'evidence/{p.name}')
        # Include help (default EN + selected languages)
        for p in HELP.iterdir():
            if p.is_file():
                z.write(p, arcname=f'help/{p.name}')
        # Autogenerated README
        readme = f'''Tenant ZIP Handoff
Tenant: {tenant_name}
Case: {case_number}

Contents:
- forms/: Answer & Counterclaim, Affidavit of Service, Motion templates
- evidence/: uploaded files
- help/: quad-lingual brief instructions

Next steps:
1) Complete Answer & Counterclaim (list each counterclaim separately).
2) Attach evidence and file via Guide & File or clerk before hearing.
3) Log in early to Zoom on the hearing date.
'''
        tmp = EXPORTS / '_README.txt'
        tmp.write_text(readme, encoding='utf-8')
        z.write(tmp, arcname='README.txt')
        tmp.unlink()

    return FileResponse(str(zip_path), filename='Tenant_ZIP_handoff.zip')
"@ | Set-Content -Path "$root/app/main.py" -Encoding UTF8

# 8) Python venv + install
Set-Location $root
python -m venv .venv
& ".\.venv\Scripts\pip.exe" install -r requirements.txt

Write-Host "Setup complete."
Write-Host "Run server: .\.venv\Scripts\python.exe app\main.py (via uvicorn)"
Write-Host "Example: .\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000"
Write-Host "Open: http://localhost:8000"
