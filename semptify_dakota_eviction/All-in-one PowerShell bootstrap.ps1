# setup_semptify_eviction.ps1
# All-in-one bootstrap for semptify-fastapi — Eviction Defense (Dakota County)
# Includes: FastAPI app, quad-lingual UI, Counterclaim Composer, evidence uploads,
# per-tenant workspaces, Guide & File link, accessibility polish,
# summary PDF (ReportLab), and true fillable-PDF field mapping (pdfrw).

$ErrorActionPreference = "Stop"

# 1) Project layout
$root = Join-Path (Get-Location) "semptify-fastapi"
$dirs = @(
    "$root/app",
    "$root/app/static",
    "$root/app/templates",
    "$root/app/assets/forms",
    "$root/app/assets/help",
    "$root/app/assets/exports",
    "$root/app/assets/evidence",
    "$root/app/assets/mappings",
    "$root/app/workspaces"
)
foreach ($d in $dirs) { if (!(Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null } }

# 2) Requirements
@"
fastapi==0.115.2
uvicorn[standard]==0.31.0
python-multipart==0.0.9
jinja2==3.1.4
pydantic==2.9.2
reportlab==4.2.2
pdfrw==0.4
"@ | Set-Content -Path "$root/requirements.txt" -Encoding UTF8

# 3) README
@"
# semptify-fastapi — Eviction Defense (Dakota County)

Features:
- Quad-lingual UI (en, es, so, ar)
- Counterclaim Composer (multiple counts)
- Evidence upload + one-click ZIP handoff
- Per-tenant workspaces (timestamped recovery)
- Summary PDF (ReportLab) and true fillable-PDF field mapping (pdfrw)
- Guide & File deep-link for Minnesota

Endpoints:
- GET / (UI) supports ?lang=en|es|so|ar
- GET /forms (catalog)
- GET /forms/file/{name} (download form)
- GET /guidefile (MN Guide & File deep-link)
- GET /help (multilingual brief help)
- POST /upload (evidence)
- POST /compose/counterclaims (save counts)
- POST /fields/summary (save field summary and fill PDFs if mapping available)
- POST /zip (build workspace ZIP)
"@ | Set-Content -Path "$root/README.md" -Encoding UTF8

# 4) Forms placeholders (replace with official PDFs)
$forms = @(
    @{ name="Answer_Counterclaim_Form.pdf"; url="https://placeholder" },
    @{ name="Affidavit_of_Service.pdf";    url="https://placeholder" },
    @{ name="Motion_to_Dismiss.pdf";       url="https://placeholder" }
)
foreach ($f in $forms) {
    $target = Join-Path "$root/app/assets/forms" $f.name
    if (!(Test-Path $target)) {
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

# 6) Field map template (JSON-configurable AcroForm mapping)
@"
{
  // Map your internal keys -> PDF field names in official Answer & Counterclaim form
  // Example keys from the app: tenant_full_name, tenant_address, landlord_name, rent_amount, notes
  // Replace the right-side strings with actual PDF field names (from the form's AcroFields)
  "tenant_full_name": "TenantName",
  "tenant_address": "TenantAddress",
  "landlord_name": "LandlordName",
  "rent_amount": "MonthlyRent",
  "notes": "FactsNotes"
}
"@ | Set-Content -Path "$root/app/assets/mappings/field_map.json" -Encoding UTF8

# 7) Accessible HTML template with composer and field summary
@"
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\"/>
  <title>Semptify Eviction Defense</title>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
  <style>
    :root { --bg:#ffffff; --text:#111; --accent:#0b5; --border:#ccc; }
    body { font-family: system-ui, Arial; margin: 1.5rem; line-height:1.6; background:var(--bg); color:var(--text); }
    .grid { display:grid; grid-template-columns: 1fr 1fr; gap:1rem; }
    @media (max-width:900px){ .grid { grid-template-columns: 1fr; } }
    .card { border:2px solid var(--border); border-radius:10px; padding:1rem; }
    button { padding:0.8rem 1.2rem; font-size:1rem; background:var(--accent); color:#fff; border:none; border-radius:8px; cursor:pointer; }
    button:focus, select:focus, input:focus, textarea:focus { outline:3px solid #333; }
    label { font-weight:700; display:block; margin-top:0.5rem; }
    input, textarea, select { width:100%; padding:0.6rem; margin-top:0.25rem; font-size:1rem; }
    .full { grid-column: 1 / -1; }
    pre { background:#f7f7f7; padding:0.75rem; border-radius:8px; }
  </style>
</head>
<body>
  <h1 id=\"title\">Semptify Eviction Defense — Dakota County</h1>

  <div class=\"grid\" role=\"region\" aria-labelledby=\"title\">
    <div class=\"card\" aria-label=\"Forms\">
      <h2>Forms</h2>
      <p>Answer & Counterclaim, Affidavit of Service, and Motion templates.</p>
      <a href=\"/forms\" target=\"_blank\" aria-label=\"View forms as JSON\"><button>View forms JSON</button></a>
      <a href=\"/guidefile\" target=\"_blank\" aria-label=\"Open Minnesota Guide and File\"><button>Open Guide & File</button></a>
    </div>

    <div class=\"card\" aria-label=\"Help text\">
      <h2>Help text</h2>
      <label for=\"lang\">Language</label>
      <select id=\"lang\" aria-label=\"Language select\">
        <option value=\"en\">English</option>
        <option value=\"es\">Español</option>
        <option value=\"so\">Somali</option>
        <option value=\"ar\">العربية</option>
      </select>
      <button onclick=\"loadHelp()\" aria-label=\"Load help text\">Load</button>
      <pre id=\"help\" style=\"white-space:pre-wrap;\" aria-live=\"polite\"></pre>
    </div>

    <div class=\"card\" aria-label=\"Evidence upload\">
      <h2>Evidence upload</h2>
      <form id=\"uploadForm\" aria-label=\"Upload evidence\">
        <input type=\"file\" name=\"file\" multiple aria-label=\"Choose files\" />
        <button type=\"submit\" aria-label=\"Upload files\">Upload</button>
      </form>
      <pre id=\"uploadStatus\" aria-live=\"polite\"></pre>
    </div>

    <div class=\"card\" aria-label=\"ZIP builder\">
      <h2>Build tenant ZIP</h2>
      <form id=\"zipForm\" aria-label=\"Generate tenant ZIP\">
        <label>Tenant name</label>
        <input name=\"tenant_name\" required aria-required=\"true\"/>
        <label>Case number</label>
        <input name=\"case_number\" required aria-required=\"true\"/>
        <label>Language</label>
        <select name=\"lang\">
          <option value=\"en\">English</option>
          <option value=\"es\">Español</option>
          <option value=\"so\">Somali</option>
          <option value=\"ar\">العربية</option>
        </select>
        <button type=\"submit\" aria-label=\"Generate ZIP\">Generate ZIP</button>
      </form>
      <div id=\"zipLink\" aria-live=\"polite\"></div>
    </div>

    <div class=\"card full\" aria-label=\"Counterclaim composer\">
      <h2>Counterclaim Composer</h2>
      <form id=\"composerForm\" aria-label=\"Compose counterclaims\">
        <div id=\"counts\"></div>
        <button type=\"button\" onclick=\"addCount()\" aria-label=\"Add counterclaim\">Add count</button>
        <button type=\"submit\" aria-label=\"Save counterclaims\">Save counterclaims</button>
      </form>
      <pre id=\"composerStatus\" aria-live=\"polite\"></pre>
    </div>

    <div class=\"card full\" aria-label=\"Field summary\">
      <h2>Fillable-field summary (Answer/Counterclaim)</h2>
      <form id=\"fieldsForm\" aria-label=\"Save fillable fields\">
        <label>Tenant full name</label>
        <input name=\"tenant_full_name\" required aria-required=\"true\"/>
        <label>Address</label>
        <input name=\"tenant_address\" required aria-required=\"true\"/>
        <label>Landlord name</label>
        <input name=\"landlord_name\" required aria-required=\"true\"/>
        <label>Rent amount</label>
        <input name=\"rent_amount\" required aria-required=\"true\"/>
        <label>Notes (conditions, repairs, etc.)</label>
        <textarea name=\"notes\"></textarea>
        <button type=\"submit\" aria-label=\"Save field summary\">Save summary</button>
      </form>
      <pre id=\"fieldsStatus\" aria-live=\"polite\"></pre>
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
  const data = new FormData(e.target);
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
    a.setAttribute('aria-label','Download ZIP');
    document.getElementById('zipLink').innerHTML = '';
    document.getElementById('zipLink').appendChild(a);
  } else {
    document.getElementById('zipLink').textContent = 'ZIP generation failed';
  }
});

function countTemplate(idx){
  return `
    <fieldset style=\"margin-bottom:1rem;\">
      <legend>Count ${idx+1}</legend>
      <label>Title (e.g., Breach of Lease, Retaliatory Eviction)</label>
      <input name=\"count_${idx}_title\" required aria-required=\"true\"/>
      <label>Facts (what happened)</label>
      <textarea name=\"count_${idx}_facts\" required aria-required=\"true\"></textarea>
      <label>Relief requested (e.g., rent abatement, dismissal)</label>
      <textarea name=\"count_${idx}_relief\" required aria-required=\"true\"></textarea>
    </fieldset>
  `;
}

function addCount(){
  const container = document.getElementById('counts');
  const idx = container.querySelectorAll('fieldset').length;
  container.insertAdjacentHTML('beforeend', countTemplate(idx));
}
addCount(); // start with one count

document.getElementById('composerForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const fields = e.target.querySelectorAll('input, textarea');
  const payload = [];
  const map = {};
  fields.forEach(f => map[f.name] = f.value);
  let i = 0;
  while(map[\`count_\${i}_title\`] !== undefined){
    payload.push({
      title: map[\`count_\${i}_title\`],
      facts: map[\`count_\${i}_facts\`],
      relief: map[\`count_\${i}_relief\`]
    });
    i++;
  }
  const res = await fetch('/compose/counterclaims', {
    method:'POST',
    headers:{ 'Content-Type':'application/json' },
    body: JSON.stringify({ counts: payload })
  });
  document.getElementById('composerStatus').textContent = await res.text();
});

document.getElementById('fieldsForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const data = new FormData(e.target);
  const res = await fetch('/fields/summary', { method:'POST', body:data });
  document.getElementById('fieldsStatus').textContent = await res.text();
});
</script>
</body>
</html>
"@ | Set-Content -Path "$root/app/templates/index.html" -Encoding UTF8

# 8) FastAPI app with true PDF mapping
@"
from fastapi import FastAPI, UploadFile, File, Form, Body
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pathlib import Path
import shutil, zipfile, json, time, os
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
import pdfrw

BASE = Path(__file__).resolve().parent
ASSETS = BASE / 'assets'
FORMS = ASSETS / 'forms'
HELP = ASSETS / 'help'
EXPORTS = ASSETS / 'exports'
EVIDENCE = ASSETS / 'evidence'
MAPPINGS = ASSETS / 'mappings'
WORKSPACES = ASSETS / 'workspaces'

app = FastAPI(title='Semptify Eviction Defense')
app.mount('/static', StaticFiles(directory=str(BASE / 'static')), name='static')
templates = Jinja2Templates(directory=str(BASE / 'templates'))

def workspace_path(tenant: str, case: str):
    ts = time.strftime('%Y%m%d_%H%M%S')
    ws = WORKSPACES / tenant / f'case_{case}' / ts
    ws.mkdir(parents=True, exist_ok=True)
    return ws

def pdf_autofill_summary(pdf_path: Path, data: dict):
    c = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    width, height = LETTER
    y = height - 72
    c.setFont('Helvetica-Bold', 14)
    c.drawString(72, y, 'Answer & Counterclaim — Field Summary')
    y -= 24
    c.setFont('Helvetica', 11)
    for k, v in [
        ('Tenant', data.get('tenant_full_name','')),
        ('Address', data.get('tenant_address','')),
        ('Landlord', data.get('landlord_name','')),
        ('Rent', data.get('rent_amount','')),
        ('Notes', data.get('notes',''))
    ]:
        c.drawString(72, y, f'{k}: {v}')
        y -= 18
    c.showPage()
    c.save()

def load_field_map():
    fp = MAPPINGS / 'field_map.json'
    if not fp.exists():
        return {}
    # Allow comments by stripping lines starting with //
    lines = []
    for line in fp.read_text(encoding='utf-8').splitlines():
        if line.strip().startswith('//'):
            continue
        lines.append(line)
    return json.loads('\n'.join(lines))

def fill_pdf_fields(input_pdf: Path, output_pdf: Path, data: dict, field_map: dict):
    # Translate internal keys -> PDF fields using field_map
    mapped = {}
    for k, v in data.items():
        pdf_field = field_map.get(k)
        if pdf_field:
            mapped[pdf_field] = v
    template = pdfrw.PdfReader(str(input_pdf))
    for page in template.pages:
        annots = page.Annots
        if not annots:
            continue
        for a in annots:
            if a.Subtype == '/Widget' and a.T:
                # Strip parentheses from field name
                name = str(a.T)[1:-1]
                if name in mapped:
                    a.V = pdfrw.objects.pdfstring.PdfString.encode(mapped[name])
                    a.AP = None
    pdfrw.PdfWriter().write(str(output_pdf), template)

@app.get('/', response_class=HTMLResponse)
def home(request: Request, lang: str = 'en'):
    return templates.TemplateResponse('index.html', { 'request': request, 'lang': lang })

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
    url = 'https://www.mncourts.gov/Help-Topics/Guide-and-File.aspx'
    return JSONResponse({'url': url, 'label': 'Minnesota Guide & File'})

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

@app.post('/compose/counterclaims')
async def compose_counterclaims(payload: dict = Body(...)):
    counts = payload.get('counts', [])
    if not counts:
        return PlainTextResponse('No counts provided', status_code=400)
    json_path = EXPORTS / 'counterclaims.json'
    txt_path = EXPORTS / 'counterclaims.txt'
    json_path.write_text(json.dumps(counts, indent=2), encoding='utf-8')
    lines = []
    for i, c in enumerate(counts, start=1):
        lines.append(f'Count {i}: {c.get("title","")}')
        lines.append('Facts:')
        lines.append(c.get('facts','').strip())
        lines.append('Relief requested:')
        lines.append(c.get('relief','').strip())
        lines.append('-' * 40)
    txt_path.write_text('\n'.join(lines), encoding='utf-8')
    return PlainTextResponse(f'Saved {len(counts)} counterclaim counts.')

@app.post('/fields/summary')
async def fields_summary(
    tenant_full_name: str = Form(...),
    tenant_address: str = Form(...),
    landlord_name: str = Form(...),
    rent_amount: str = Form(...),
    notes: str = Form('')
):
    summary = {
        'tenant_full_name': tenant_full_name,
        'tenant_address': tenant_address,
        'landlord_name': landlord_name,
        'rent_amount': rent_amount,
        'notes': notes
    }
    EXPORTS.mkdir(parents=True, exist_ok=True)
    (EXPORTS / 'fillable_fields_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (EXPORTS / 'fillable_fields_summary.txt').write_text(
        f'Tenant: {tenant_full_name}\nAddress: {tenant_address}\nLandlord: {landlord_name}\nRent: {rent_amount}\nNotes: {notes}\n',
        encoding='utf-8'
    )
    pdf_path = EXPORTS / 'fillable_fields_summary.pdf'
    pdf_autofill_summary(pdf_path, summary)

    # True PDF field mapping if template + mapping exist
    form_template = FORMS / 'Answer_Counterclaim_Form.pdf'
    field_map = load_field_map()
    filled_pdf = EXPORTS / 'Answer_Counterclaim_Filled.pdf'
    if form_template.exists() and field_map:
        try:
            fill_pdf_fields(form_template, filled_pdf, summary, field_map)
        except Exception as e:
            (EXPORTS / 'pdf_fill_error.txt').write_text(str(e), encoding='utf-8')

    return PlainTextResponse('Field summary saved (JSON, TXT, PDF). If mapping and template exist, filled PDF generated.')

@app.post('/zip')
async def build_zip(
    tenant_name: str = Form(...),
    case_number: str = Form(...),
    lang: str = Form('en')
):
    ws = workspace_path(tenant_name, case_number)
    def copy_dir(src: Path, dest: Path):
        dest.mkdir(parents=True, exist_ok=True)
        for p in src.iterdir():
            if p.is_file():
                shutil.copy2(p, dest / p.name)
    copy_dir(FORMS, ws / 'forms')
    copy_dir(EVIDENCE, ws / 'evidence')
    copy_dir(HELP, ws / 'help')
    copy_dir(EXPORTS, ws / 'exports')

    readme = f'''Tenant Workspace
Tenant: {tenant_name}
Case: {case_number}
Language: {lang}

Snapshot contents:
- forms/: Answer & Counterclaim, Affidavit of Service, Motion templates
- evidence/: uploaded files
- help/: brief instructions
- exports/: counterclaims, field summaries, PDFs (including filled form if mapping works)

Use the filled Answer & Counterclaim PDF if present.
If not, use the summary PDF/TXT and manually transfer into the official form.
'''
    (ws / 'README.txt').write_text(readme, encoding='utf-8')

    zip_path = ws / 'Tenant_ZIP_handoff.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(ws):
            for name in files:
                p = Path(root) / name
                if p == zip_path: 
                    continue
                arc = str(p.relative_to(ws))
                z.write(p, arcname=arc)

    return FileResponse(str(zip_path), filename='Tenant_ZIP_handoff.zip')
"@ | Set-Content -Path "$root/app/main.py" -Encoding UTF8

# 9) Python venv + install
Set-Location $root
python -m venv .venv
& ".\.venv\Scripts\pip.exe" install -r requirements.txt

Write-Host "Setup complete."
Write-Host "Run server (dev): .\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000"
Write-Host "Open: http://localhost:8000?lang=en"
