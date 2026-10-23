const path = require('path');
const root = path.resolve(__dirname, '..');
const esbuild = require(path.join(root, 'mobile/node_modules/esbuild'));
for (const [source, globalName, target] of [
  ['calculator-shield.ts', 'CalculatorShieldModel', 'calculator-shield-model.js'],
  ['calculator-trait-model.ts', 'CalculatorTraitModel', 'calculator-trait-model.js'],
  ['deck-rules.ts', 'DeckRules', 'deck-rules-model.js'],
]) esbuild.buildSync({entryPoints:[path.join(root,'mobile/src',source)],bundle:true,format:'iife',globalName,target:'es2021',minify:true,outfile:path.join(root,'LumenGG/static/v2',target)});
