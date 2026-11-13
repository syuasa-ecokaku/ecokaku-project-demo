"""Load pinned public browser-test assets through the environment's trusted TLS client.
Chromium's separate certificate store may not include the managed proxy CA.
This keeps TLS verification enabled; the application itself is not modified.
"""
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen
URLS=[
 'https://unpkg.com/@floating-ui/core@1.7.3/dist/floating-ui.core.umd.min.js',
 'https://unpkg.com/@floating-ui/dom@1.7.4/dist/floating-ui.dom.umd.min.js',
 'https://unpkg.com/lucide@1.17.0/dist/umd/lucide.js',
]
def verified_cdn(page):
 cache=Path('/tmp/ecokaku-verified-test-assets');cache.mkdir(exist_ok=True)
 for url in URLS:
  path=cache/sha256(url.encode()).hexdigest()
  if not path.exists():
   with urlopen(url,timeout=20) as response:path.write_bytes(response.read())
  page.route(url,lambda route,request,path=path:route.fulfill(body=path.read_bytes(),content_type='application/javascript'))
