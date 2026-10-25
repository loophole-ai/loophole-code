// Usage: node unzip_vsix.cjs <file.vsix> <outDir> [requireFrom]
// Extracts the `extension/` folder of a .vsix into outDir. Uses yauzl (a dependency of @vscode/vsce),
// so it works the same on Linux, macOS and Windows runners without needing `unzip`.
const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');
const [vsix, outDir, requireFrom = process.cwd()] = process.argv.slice(2);
if (!vsix || !outDir) { console.error('usage: unzip_vsix.cjs <vsix> <outDir> [requireFrom]'); process.exit(2); }
const req = createRequire(path.join(path.resolve(requireFrom), 'noop.js'));
const vsceReq = createRequire(req.resolve('@vscode/vsce'));
const yauzl = vsceReq('yauzl');
const root = path.resolve(outDir);
fs.mkdirSync(root, { recursive: true });
yauzl.open(vsix, { lazyEntries: true }, (err, zip) => {
	if (err) { console.error(err); process.exit(1); }
	let files = 0;
	zip.on('error', e => { console.error(e); process.exit(1); });
	zip.on('end', () => { console.log(`extracted ${files} files to ${root}`); });
	zip.readEntry();
	zip.on('entry', entry => {
		const m = /^extension\/(.*)$/.exec(entry.fileName);
		if (!m || m[1] === '' || entry.fileName.endsWith('/')) { return zip.readEntry(); }
		const target = path.join(root, m[1]);
		if (!target.startsWith(root + path.sep)) { return zip.readEntry(); } // zip-slip guard
		fs.mkdirSync(path.dirname(target), { recursive: true });
		zip.openReadStream(entry, (e, stream) => {
			if (e) { console.error(e); process.exit(1); }
			stream.pipe(fs.createWriteStream(target)).on('close', () => { files++; zip.readEntry(); });
		});
	});
});
