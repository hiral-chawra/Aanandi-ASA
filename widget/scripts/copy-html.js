import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.resolve(__dirname, '../index.html');
const distDir = path.resolve(__dirname, '../dist');
const distHtmlPath = path.resolve(distDir, 'index.html');

if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}

let html = fs.readFileSync(htmlPath, 'utf-8');
// Replace dev module script with production bundle
html = html.replace(
  /<script\s+type="module"\s+src="\/src\/index\.tsx"><\/script>/i,
  '<script src="/widget.min.js"></script>'
);
// Remove hardcoded localhost api-base attribute so it auto-detects current host origin
html = html.replace(/\s*api-base="http:\/\/localhost:8000"/i, '');

fs.writeFileSync(distHtmlPath, html, 'utf-8');
console.log('Production index.html generated in dist/');
