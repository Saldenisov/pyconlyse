// Render stored lvkit SVG to PNG; this does not capture a LabVIEW window.
const sharp = require("sharp");
const [input, output] = process.argv.slice(2);
if (!input || !output) throw new Error("Usage: node rasterize_lvkit_svg.cjs input.svg output.png");
sharp(input, { density: 192 }).png().toFile(output)
  .then(info => process.stdout.write(JSON.stringify(info) + "\n"))
  .catch(error => { process.stderr.write(error.message + "\n"); process.exitCode = 1; });
