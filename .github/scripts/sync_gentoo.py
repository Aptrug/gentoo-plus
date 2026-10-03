import sys
import os
import shutil
import tempfile
import hashlib
import urllib.request
import json
import time
import subprocess
import asyncio
import atexit
from concurrent.futures import ThreadPoolExecutor, as_completed

gentoo_url = "https://anongit.gentoo.org/git/repo/gentoo.git"
xlibre_url = "https://github.com/X11Libre/ports-gentoo.git"
vim_ebuild_src = ".github/ebuilds/vim.ebuild"
vim_dir = "app-editors/vim"
norminette_ebuild_src = ".github/ebuilds/norminette.ebuild"
norminette_dir = "dev-util/norminette"
brave_ebuild_src = ".github/ebuilds/brave-origin.ebuild"
brave_dir = "www-client/brave-origin"
helium_ebuild_src = ".github/ebuilds/helium-browser.ebuild"
helium_dir = "www-client/helium-browser"
kernel_ebuild_src = ".github/ebuilds/linux-lts.ebuild"
kernel_dir = "sys-kernel/linux-lts"
chrome_ebuild_src = ".github/ebuilds/google-chrome.ebuild"
chrome_dir = "www-client/google-chrome"
limine_ebuild_src = ".github/ebuilds/limine-bin.ebuild"
limine_dir = "sys-boot/limine-bin"
tmp_tree = "/tmp/merged_tree"
tmp_github = "/tmp/dot-github"
sha_file = ".github/last-sync-shas"
gentoo_bare = "/tmp/gentoo-bare"
xlibre_bare = "/tmp/xlibre-bare"

DOWNLOAD_WORKERS = 16

def download_file(url, dest):
	try:
		# Probe: get Content-Length and confirm the server honours Range requests
		head = urllib.request.Request(url, method='HEAD')
		head.add_header('User-Agent', 'curl/8.5.0')
		with urllib.request.urlopen(head, timeout=30) as r:
			size = int(r.headers.get('Content-Length') or 0)
			ranges_ok = r.headers.get('Accept-Ranges', 'none').strip().lower() == 'bytes'

		if not size or not ranges_ok:
			# Server doesn't support ranges; plain single-connection fallback.
			req = urllib.request.Request(url)
			req.add_header('User-Agent', 'curl/8.5.0')
			with urllib.request.urlopen(req, timeout=60) as r, open(dest, 'wb') as f:
				shutil.copyfileobj(r, f)
			return

		# Pre-allocate the output file so threads can write at arbitrary offsets.
		with open(dest, 'wb') as f:
			f.seek(size - 1)
			f.write(b'\x00')

		chunk_size = -(-size // DOWNLOAD_WORKERS)  # ceiling division — last chunk may be smaller

		def fetch_chunk(i):
			start = i * chunk_size
			if start >= size:
				return
			end = min(start + chunk_size - 1, size - 1)
			req = urllib.request.Request(url)
			req.add_header('User-Agent', 'curl/8.5.0')
			req.add_header('Range', f'bytes={start}-{end}')
			with urllib.request.urlopen(req, timeout=60) as r:
				data = r.read()
			# Each thread opens its own fd so seek+write are independent.
			with open(dest, 'r+b') as f:
				f.seek(start)
				f.write(data)

		with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
			futures = [pool.submit(fetch_chunk, i) for i in range(DOWNLOAD_WORKERS)]
			for fut in as_completed(futures):
				fut.result()  # re-raises any exception from a worker thread
	except urllib.error.HTTPError as e:
		log(f"HTTP {e.code} {e.reason}: {url}")
		raise

def write_manifest_append(manifest_path, exclude_prefix, new_line):
	lines = []
	if os.path.exists(manifest_path):
		with open(manifest_path) as f:
			content = f.read()
		lines = [line for line in content.splitlines() if not line.startswith(exclude_prefix)]
	lines.append(new_line)
	with open(manifest_path, 'w') as f:
		f.write('\n'.join(lines) + '\n')

def install_ebuild(tree, pkg):
	pkg_dir = os.path.join(tree, pkg['tree_dir'])
	os.makedirs(pkg_dir, exist_ok=True)
	metadata_path = os.path.join(pkg_dir, 'metadata.xml')
	with open(metadata_path, 'w') as f:
		f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
			'<!DOCTYPE pkgmetadata SYSTEM "https://www.gentoo.org/dtd/metadata.dtd">\n'
			'<pkgmetadata>\n'
			'\t<maintainer type="person" proxied="yes">\n'
			'\t\t<email>anon@anon.org</email>\n'
			'\t\t<name>anon</name>\n'
			'\t</maintainer>\n'
			'</pkgmetadata>\n')
	prefix = pkg['ebuild_prefix']
	for fname in list(os.listdir(pkg_dir)):
		if fname.startswith(prefix) and fname.endswith('.ebuild'):
			os.remove(os.path.join(pkg_dir, fname))
	with open(os.path.join(pkg_dir, f"{prefix}{pkg['ver']}.ebuild"), 'w') as f:
		f.write(pkg['ebuild_content'])
	h = pkg['hashes']
	dist_line = f"DIST {pkg['tarball']} {h['size']} BLAKE2B {h['blake2b']} SHA512 {h['sha512']}"
	manifest_path = os.path.join(pkg_dir, 'Manifest')
	if pkg['manifest_exclude']:
		write_manifest_append(manifest_path, pkg['manifest_exclude'], dist_line)
	else:
		with open(manifest_path, 'w') as f:
			f.write(dist_line + '\n')

def log(*args):
	print(f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}]", *args, flush=True)

MAX_TRIES = 3

def bare_fetch(name, url, directory, current_sha, last_sha):
	if current_sha == last_sha and os.path.isdir(directory):
		log(f"{name} SHA unchanged, skipping fetch.")
		return
	updating = os.path.isdir(directory)
	verb = "fetch" if updating else "clone"
	log(f"{'Updating' if updating else 'Creating'} {name} bare clone...")
	for attempts_left in range(MAX_TRIES, 0, -1):
		try:
			if updating:
				git('-C', directory, 'fetch', '--depth=1', '--verbose', '--force', 'origin', 'master:master')
			else:
				git('clone', '--bare', '--depth=1', '--verbose', url, directory)
			return
		except subprocess.CalledProcessError:
			if attempts_left == 1:
				log(f"ERROR: failed to {verb} {name} after {MAX_TRIES} attempts")
				sys.exit(1)
			if not updating:
				shutil.rmtree(directory, ignore_errors=True)
			log(f"Retrying {name} {verb} ({attempts_left - 1} attempts left)...")
			time.sleep(10)

def hash_file(filepath):
	size = str(os.path.getsize(filepath))
	b2 = hashlib.blake2b()
	sha512 = hashlib.sha512()
	with open(filepath, 'rb') as f:
		while chunk := f.read(65536):
			b2.update(chunk)
			sha512.update(chunk)
	return size, b2.hexdigest(), sha512.hexdigest()

def read_ebuild(path):
	with open(path) as f:
		return f.read()

def cleanup_tmp():  # for atexit
	for pkg in packages:
		path = pkg.get('tmp_path')
		if path:
			try:
				os.remove(path)
			except OSError:
				pass

async def run_probe():
	log("Probing upstream...")

	# Load previous state so we can compute 'changed'
	state = {}
	if os.path.isfile(sha_file):
		with open(sha_file) as f:
			try:
				state = json.load(f)
			except (json.JSONDecodeError, ValueError):
				pass

	last_gentoo = state.get('gentoo', '')
	last_xlibre = state.get('xlibre', '')

	def last_ver(key):
		return state.get(key, {}).get('ver', '')

	def fetch_json(url):
		req = urllib.request.Request(url)
		req.add_header('User-Agent', 'curl/8.5.0')
		token = os.environ.get('GITHUB_TOKEN')
		if token and 'api.github.com' in url:
			req.add_header('Authorization', f'Bearer {token}')
		with urllib.request.urlopen(req, timeout=30) as r:
			return json.loads(r.read().decode())

	def _get_brave():
		data = fetch_json('https://api.github.com/repos/brave/brave-browser/releases/latest')
		ver = data['tag_name'].lstrip('v')
		names = {a['name'] for a in data['assets']}
		if f"brave-origin-{ver}-linux-amd64.zip" not in names:
			log(f"brave {ver} has no linux amd64 asset yet, staying on {last_ver('brave')}")
			return last_ver('brave')
		return ver

	def get_gentoo_sha():
		for attempt in range(1, MAX_TRIES + 1):
			try:
				return subprocess.check_output(
					['git', 'ls-remote', gentoo_url, 'refs/heads/master'],
					text=True, timeout=20
				).split()[0]
			except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
				if attempt == MAX_TRIES:
					raise
				log(f"git ls-remote gentoo failed (attempt {attempt}/{MAX_TRIES}), retrying in 10s...")
				time.sleep(10)

	def get_xlibre_sha():
		# GitHub has a REST API — faster and lighter than git ls-remote
		data = fetch_json('https://api.github.com/repos/X11Libre/ports-gentoo/branches/master')
		return data['commit']['sha']

	def get_kernel():
		with urllib.request.urlopen("https://www.kernel.org/releases.json") as r:
			releases = json.load(r)["releases"]
		lts = next(r for r in releases if r["moniker"] == "longterm")
		return lts["version"]

	def get_vim():
		req = urllib.request.Request('https://archlinux.org/packages/extra/x86_64/vim/download/', method='HEAD')
		req.add_header('User-Agent', 'curl/8.5.0')
		with urllib.request.urlopen(req, timeout=30) as r:
			return r.url.split('/')[-1].split('vim-')[1].split('-')[0]

	gentoo_sha, xlibre_sha, vim_ver, norminette_ver, brave_ver, helium_ver, kernel_ver, limine_ver = await asyncio.gather(
		asyncio.to_thread(get_gentoo_sha),
		asyncio.to_thread(get_xlibre_sha),
		asyncio.to_thread(get_vim),
		asyncio.to_thread(lambda: fetch_json('https://api.github.com/repos/42School/norminette/releases/latest')['tag_name'].lstrip('v')),
		asyncio.to_thread(lambda: _get_brave()),
		asyncio.to_thread(lambda: fetch_json('https://api.github.com/repos/imputnet/helium-linux/releases/latest')['tag_name'].lstrip('v')),
		asyncio.to_thread(get_kernel),
		asyncio.to_thread(lambda: fetch_json('https://api.github.com/repos/Limine-Bootloader/Limine/releases/latest')['tag_name'].lstrip('v')),
	)

	changed = not (
		gentoo_sha == last_gentoo and
		xlibre_sha == last_xlibre and
		vim_ver == last_ver('vim') and
		norminette_ver == last_ver('norminette') and
		brave_ver == last_ver('brave') and
		helium_ver == last_ver('helium') and
		kernel_ver == last_ver('kernel') and
		limine_ver == last_ver('limine')
	)

	with open(os.environ.get("GITHUB_OUTPUT", "/dev/stdout"), "a") as f:
		f.write(f"gentoo={gentoo_sha}\n")
		f.write(f"xlibre={xlibre_sha}\n")
		f.write(f"vim={vim_ver}\n")
		f.write(f"norminette={norminette_ver}\n")
		f.write(f"brave={brave_ver}\n")
		f.write(f"helium={helium_ver}\n")
		f.write(f"kernel={kernel_ver}\n")
		f.write(f"limine={limine_ver}\n")
		f.write(f"changed={str(changed).lower()}\n")

if len(sys.argv) > 1 and sys.argv[1] == "probe":
	asyncio.run(run_probe())
	sys.exit(0)

def git(*args):
	subprocess.run(['git', *args], check=True)

git('config', '--global', 'user.email', 'actions@github.com')
git('config', '--global', 'user.name', 'github-actions')
git('config', '--global', 'checkout.workers', str(os.cpu_count()))
git('config', '--global', 'index.threads',    str(os.cpu_count()))

gentoo_sha = os.environ.get("GENTOO_SHA", "")
xlibre_sha = os.environ.get("XLIBRE_SHA", "")
vim_ver = os.environ.get("VIM_VER", "")
norminette_ver = os.environ.get("NORMINETTE_VER", "")
brave_ver = os.environ.get("BRAVE_VER", "")
helium_ver = os.environ.get("HELIUM_VER", "")
kernel_ver = os.environ.get("KERNEL_VER", "")
limine_ver = os.environ.get("LIMINE_VER", "")

state = {}
if os.path.isfile(sha_file):
	with open(sha_file) as f:
		try:
			state = json.load(f)
		except (json.JSONDecodeError, ValueError):
			log("Warning: state file unreadable or old format, treating all as changed.")

last_gentoo = state.get('gentoo', '')
last_xlibre = state.get('xlibre', '')

def last_ver(key):
	return state.get(key, {}).get('ver', '')

def last_hashes(key):
	s = state.get(key, {})
	return s.get('size', ''), s.get('blake2b', ''), s.get('sha512', '')

def run_gather(tasks):
	async def _inner():
		await asyncio.gather(*tasks)
	asyncio.run(_inner())

# --- package table (replaces all tarball URL variables and scattered last_* vars) ---
packages = [
	{
		'key':			'vim',
		'ver':			vim_ver,
		'last_ver':		last_ver('vim'),
		'tarball':		f"vim-{vim_ver}.tar.gz",
		'url':			f"https://github.com/vim/vim/archive/refs/tags/v{vim_ver}.tar.gz",
		'ebuild_src':		vim_ebuild_src,
		'tree_dir':		vim_dir,
		'ebuild_prefix':	'vim-',
		'manifest_exclude':	'DIST vim-', # preserve other DIST lines in upstream Manifest
		'hashes':		dict(zip(('size', 'blake2b', 'sha512'), last_hashes('vim'))),
	},
	{
		'key':			'norminette',
		'ver':			norminette_ver,
		'last_ver':		last_ver('norminette'),
		'tarball':		f"norminette-{norminette_ver}.tar.gz",
		'url':			f"https://github.com/42School/norminette/archive/refs/tags/{norminette_ver}.tar.gz",
		'ebuild_src':		norminette_ebuild_src,
		'tree_dir':		norminette_dir,
		'ebuild_prefix':	'norminette-',
		'manifest_exclude':	None, # injected dir, overwrite Manifest entirely
		'hashes':		dict(zip(('size', 'blake2b', 'sha512'), last_hashes('norminette'))),
	},
	{
		'key':			'brave',
		'ver':			brave_ver,
		'last_ver':		last_ver('brave'),
		'tarball':		f"brave-origin-{brave_ver}-linux-amd64.zip",
		'url':			f"https://github.com/brave/brave-browser/releases/download/v{brave_ver}/brave-origin-{brave_ver}-linux-amd64.zip",
		'ebuild_src':		brave_ebuild_src,
		'tree_dir':		brave_dir,
		'ebuild_prefix':	'brave-origin-',
		'manifest_exclude':	None, # injected dir, overwrite Manifest entirely
		'hashes':		dict(zip(('size', 'blake2b', 'sha512'), last_hashes('brave'))),
	},
{
		'key':			'helium',
		'ver':			helium_ver,
		'last_ver':		last_ver('helium'),
		'tarball':		f"helium-{helium_ver}-x86_64_linux.tar.xz",
		'url':			f"https://github.com/imputnet/helium-linux/releases/download/{helium_ver}/helium-{helium_ver}-x86_64_linux.tar.xz",
		'ebuild_src':		helium_ebuild_src,
		'tree_dir':		helium_dir,
		'ebuild_prefix':	'helium-browser-',
		'manifest_exclude':	None,
		'hashes':		dict(zip(('size', 'blake2b', 'sha512'), last_hashes('helium'))),
	},
	{
		'key':			'kernel',
		'ver':			kernel_ver,
		'last_ver':		last_ver('kernel'),
		'tarball':		f"linux-{kernel_ver}.tar.xz",
		'url':			f"https://cdn.kernel.org/pub/linux/kernel/v{kernel_ver.split('.')[0]}.x/linux-{kernel_ver}.tar.xz",
		'ebuild_src':		kernel_ebuild_src,
		'tree_dir':		kernel_dir,
		'ebuild_prefix':	'linux-lts-',
		'manifest_exclude':	None,
		'hashes':		dict(zip(('size', 'blake2b', 'sha512'), last_hashes('kernel'))),
	},
	{
		'key':			'limine',
		'ver':			limine_ver,
		'last_ver':		last_ver('limine'),
		'tarball':		'limine-binary.tar.xz',
		'url':			f"https://github.com/Limine-Bootloader/Limine/releases/download/v{limine_ver}/limine-binary.tar.xz",
		'ebuild_src':		limine_ebuild_src,
		'tree_dir':		limine_dir,
		'ebuild_prefix':	'limine-bin-',
		'manifest_exclude':	None,
		'hashes':		dict(zip(('size', 'blake2b', 'sha512'), last_hashes('limine'))),
	},
]

if (gentoo_sha == last_gentoo and xlibre_sha == last_xlibre
		and all(pkg['ver'] == pkg['last_ver'] for pkg in packages)):
	log(f"Upstream unchanged, exiting.")
	sys.exit(0)

log("Changes detected, syncing...")

atexit.register(cleanup_tmp)

shutil.rmtree(tmp_github, ignore_errors=True)
shutil.copytree(".github", tmp_github)

# Read ebuilds now — .github/ebuilds/ is never touched by bare_fetch or git rm.
for pkg in packages:
	pkg['ebuild_content'] = read_ebuild(pkg['ebuild_src'])

# Build download tasks alongside the bare-fetch tasks; they're fully independent.
dl_tasks = []
for pkg in packages:
	if pkg['ver'] != pkg['last_ver']:
		fd, path = tempfile.mkstemp()
		os.close(fd)
		pkg['tmp_path'] = path
		dl_tasks.append(asyncio.to_thread(download_file, pkg['url'], path))

concurrent_tasks = [
	asyncio.to_thread(bare_fetch, "gentoo", gentoo_url, gentoo_bare, gentoo_sha, last_gentoo),
	asyncio.to_thread(bare_fetch, "xlibre", xlibre_url, xlibre_bare, xlibre_sha, last_xlibre),
	*dl_tasks,
]
log("Fetching repos" + (" and downloading tarballs concurrently" if dl_tasks else "") + "...")
run_gather(concurrent_tasks)

log("Building merged tree...")
shutil.rmtree(tmp_tree, ignore_errors=True)
os.makedirs(tmp_tree)
git('--git-dir=' + gentoo_bare, '--work-tree=' + tmp_tree, 'checkout', 'master', '--', '.')
for _d in (os.path.join('x11-base', 'xorg-server'), os.path.join('gui-libs', 'display-manager-init'), 'x11-drivers'):
	shutil.rmtree(os.path.join(tmp_tree, _d), ignore_errors=True)

git('--git-dir=' + xlibre_bare, '--work-tree=' + tmp_tree, 'checkout', 'master', '--', 'x11-base', 'x11-drivers', 'gui-libs/display-manager-init', 'eclass')
shutil.rmtree(f"{tmp_tree}/.github", ignore_errors=True)

chrome_content = read_ebuild(chrome_ebuild_src)
for fname in os.listdir(os.path.join(tmp_tree, chrome_dir)):
	if fname.endswith('.ebuild'):
		with open(os.path.join(tmp_tree, chrome_dir, fname), 'w') as f:
			f.write(chrome_content)

mesa_dir = "media-libs/mesa"
for fname in os.listdir(os.path.join(tmp_tree, mesa_dir)):
	if fname.endswith('.ebuild'):
		fpath = os.path.join(tmp_tree, mesa_dir, fname)
		with open(fpath) as f:
			content = f.read()
		with open(fpath, 'w') as f:
			f.write(content.replace("llvm_targets_AMDGPU(+),", ''))

lld_dir = os.path.join(tmp_tree, 'llvm-core', 'lld')
for fname in os.listdir(lld_dir):
	if fname.endswith('.ebuild'):
		p = os.path.join(lld_dir, fname)
		with open(p) as f:
			content = f.read()
		with open(p, 'w') as f:
			f.write(content.replace('LLVM_USE_TARGETS=llvm+eq\n', ''))

# clang_common_dir = os.path.join(tmp_tree, 'llvm-core', 'clang-common')
# for fname in os.listdir(clang_common_dir):
# 	if fname.endswith('.ebuild'):
# 		p = os.path.join(clang_common_dir, fname)
# 		content = open(p).read()
# 		open(p, 'w').write(content.replace('!llvm-libunwind? ( sys-libs/libunwind[static-libs] )', ''))
#
# clang_unwindlib_dir = os.path.join(tmp_tree, 'llvm-runtimes', 'clang-unwindlib-config')
# for fname in os.listdir(clang_unwindlib_dir):
# 	if fname.endswith('.ebuild'):
# 		p = os.path.join(clang_unwindlib_dir, fname)
# 		content = open(p).read()
# 		open(p, 'w').write(content.replace('!llvm-libunwind? ( sys-libs/libunwind[static-libs] )', ''))

async def _hash_pkg(pkg):
	path = pkg.get('tmp_path')
	if path:
		log(f"{pkg['key']} version changed to {pkg['ver']}, hashing...")
		size, b2, sha = await asyncio.to_thread(hash_file, path)
		pkg['hashes'] = {'size': size, 'blake2b': b2, 'sha512': sha}
	else:
		log(f"{pkg['key']} unchanged ({pkg['ver']}), reusing cached hashes.")
run_gather([_hash_pkg(pkg) for pkg in packages])

for pkg in packages:
	log(f"{pkg['key']}: installing ebuild and manifest...")
	install_ebuild(tmp_tree, pkg)

make_defaults = os.path.join(tmp_tree, 'profiles', 'base', 'make.defaults')
with open(make_defaults) as f:
	defaults_content = f.read()
py_target = next(
	line.split('=', 1)[1].strip().strip('"')
	for line in defaults_content.splitlines()
	if line.startswith('PYTHON_SINGLE_TARGET=')
)
for fname in os.listdir(os.path.join(tmp_tree, norminette_dir)):
	if fname.endswith('.ebuild'):
		p = os.path.join(tmp_tree, norminette_dir, fname)
		with open(p) as f:
			content = f.read()
		with open(p, 'w') as f:
			f.write(content.replace('python3_10', py_target))

now = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())

versions = ' + '.join(f"{pkg['key']}-{pkg['ver']}" for pkg in packages)
commit_msg = f"[{now}] gentoo + xlibre + {versions}"

new_state = {'gentoo': gentoo_sha, 'xlibre': xlibre_sha}
for pkg in packages:
	new_state[pkg['key']] = {'ver': pkg['ver'], **pkg['hashes']}
with open(f"{tmp_github}/last-sync-shas", 'w') as f:
	json.dump(new_state, f, indent=2)
	f.write('\n')

git('sparse-checkout', 'disable')

log("Creating orphan commit...")
git('checkout', '--orphan', 'master_new')
git('rm', '-rf', '.', '--quiet')

for item in os.listdir(tmp_tree):
	s = os.path.join(tmp_tree, item)
	d = os.path.join(".", item)
	if os.path.isdir(s):
		shutil.copytree(s, d, dirs_exist_ok=True)
	else:
		shutil.copy2(s, d)

shutil.copytree(tmp_github, ".github")

git('add', '-A')
git('commit', '-q', '-m', commit_msg)
git('branch', '-D', 'master')
git('branch', '-m', 'master_new', 'master')

log("Pushing...")
git('push', '--force', 'origin', 'master')
log("Done.")
