import os

# All hrefs from shared-nav.js (extracted manually)
nav_hrefs = [
    '/static/dashboard.html',
    '/static/crisis_intake.html',
    '/static/journey.html',
    '/static/document_intake.html',
    '/static/timeline.html',
    '/static/timeline_auto_build.html',
    '/static/timeline-builder.html',
    '/static/law_library.html',
    '/static/legal_analysis.html',
    '/static/legal_trails.html',
    '/static/court_learning.html',
    '/static/dakota_defense.html',
    '/static/eviction_answer.html',
    '/static/counterclaim.html',
    '/static/motions.html',
    '/static/hearing_prep.html',
    '/static/zoom_court.html',
    '/static/documents.html',
    '/static/briefcase.html',
    '/static/court_packet.html',
    '/static/pdf_tools.html',
    '/static/recognition.html',
    '/static/brain.html',
    '/static/complaints.html',
    '/static/calendar.html',
    '/static/contacts.html',
    '/static/research.html',
    '/static/crawler.html',
    '/static/funding_search.html',
    '/static/help.html',
    '/static/mesh_network.html',
    '/static/storage_setup.html',
    '/static/privacy.html',
    '/static/evaluation_report.html',
]

# Extract just filenames
nav_files = set(h.split('/')[-1].split('?')[0] for h in nav_hrefs)

# List HTML files in static
static_path = r'c:\Semptify\Semptify-FastAPI\static'
html_files = set(f for f in os.listdir(static_path) if f.endswith('.html'))

# Find files NOT in nav
missing = sorted(html_files - nav_files)

# Print to stdout
print('=' * 60)
print(f'HTML FILES NOT IN NAVIGATION ({len(missing)} files):')
print('=' * 60)
for item in missing:
    print(f'  - {item}')
print()
print('=' * 60)
print(f'TOTAL HTML FILES: {len(html_files)}')
print(f'IN NAVIGATION: {len(nav_files)}')
print(f'NOT IN NAV: {len(missing)}')
print('=' * 60)
print()
print('ALL HTML FILES:')
for f in sorted(html_files):
    print(f'  {f}')
