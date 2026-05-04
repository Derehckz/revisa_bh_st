import fs from "node:fs";
import path from "node:path";

const distAssets = path.resolve("dist", "assets");
if (!fs.existsSync(distAssets)) {
  console.error("No existe dist/assets. Ejecuta 'npm run build' primero.");
  process.exit(1);
}

const limits = {
  maxAnyJsKb: 900,
  maxCssKb: 80,
  maxVendorChartsKb: 420,
};

const files = fs.readdirSync(distAssets);
const jsFiles = files.filter((f) => f.endsWith(".js"));
const cssFiles = files.filter((f) => f.endsWith(".css"));

const sizeKb = (filePath) => fs.statSync(filePath).size / 1024;
const violations = [];

for (const file of jsFiles) {
  const full = path.join(distAssets, file);
  const kb = sizeKb(full);
  if (kb > limits.maxAnyJsKb) {
    violations.push(`JS ${file} = ${kb.toFixed(2)}KB > ${limits.maxAnyJsKb}KB`);
  }
  if (file.includes("vendor-charts") && kb > limits.maxVendorChartsKb) {
    violations.push(`Charts chunk ${file} = ${kb.toFixed(2)}KB > ${limits.maxVendorChartsKb}KB`);
  }
}

for (const file of cssFiles) {
  const full = path.join(distAssets, file);
  const kb = sizeKb(full);
  if (kb > limits.maxCssKb) {
    violations.push(`CSS ${file} = ${kb.toFixed(2)}KB > ${limits.maxCssKb}KB`);
  }
}

if (violations.length > 0) {
  console.error("Bundle budget FAILED:");
  for (const v of violations) console.error(` - ${v}`);
  process.exit(1);
}

console.log("Bundle budget OK.");
