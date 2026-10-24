"""Download credited stock photography used only for fictional demo content."""
import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'static' / 'demo'
assets = json.loads((DIRECTORY / 'credits.json').read_text(encoding='utf-8'))

def fetch(asset):
    path = DIRECTORY / (asset['name'] + '.jpg')
    if path.exists():
        return f'{asset["name"]}: already downloaded'
    avatar = asset['name'].startswith('avatar-')
    query = 'auto=format&fit=crop&w=480&h=480&q=85' if avatar else 'auto=format&fit=max&w=1400&q=85'
    url = f'https://images.unsplash.com/{asset["photo"]}?{query}'
    with urlopen(Request(url, headers={'User-Agent': 'SnapMix-Demo/1.0'}), timeout=45) as response:
        image = ImageOps.exif_transpose(Image.open(BytesIO(response.read()))).convert('RGB')
        image.thumbnail((1400, 1400))
        image.save(path, 'JPEG', quality=88, optimize=True)
    return f'{asset["name"]}: saved {image.width}x{image.height}'

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(fetch, assets):
            print(result)
