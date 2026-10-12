import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import ts from 'typescript';
import { expect, it } from 'vitest';

const website = resolve(import.meta.dirname, '../../..');
const version = '20261011-live-recovery';
function imports(file: string) {
  const source = ts.createSourceFile(file, readFileSync(resolve(website, file), 'utf8'),
    ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  return source.statements.filter(ts.isImportDeclaration)
    .map((node) => (node.moduleSpecifier as ts.StringLiteral).text);
}

it('invalidates the complete legacy Live import chain with one shared tonight module', () => {
  const document = new DOMParser().parseFromString(readFileSync(resolve(website, 'index.html'), 'utf8'), 'text/html');
  expect(document.querySelector('script[type="module"][src^="js/app.js"]')?.getAttribute('src'))
    .toBe(`js/app.js?v=${version}`);
  expect(imports('js/app.js')).toContain(`./tonight.js?v=${version}`);
  expect(imports('js/app.js')).toContain(`./home.js?v=${version}`);
  expect(imports('js/home.js')).toContain(`./tonight.js?v=${version}`);
  expect(imports('js/tonight.js')).toContain(`./live-ticker.js?v=${version}`);
});
