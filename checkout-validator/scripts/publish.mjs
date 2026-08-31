import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));
const raiz = resolve(aqui, "..");
const origem = resolve(raiz, "dist", "main.js");
const destino = resolve(raiz, "..", "public", "checkout-validator.js");

await mkdir(resolve(raiz, "..", "public"), { recursive: true });
await copyFile(origem, destino);
console.log(`Publicado: ${destino}`);
