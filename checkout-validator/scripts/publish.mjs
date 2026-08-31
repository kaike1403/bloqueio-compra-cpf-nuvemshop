import { copyFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const raiz = resolve(import.meta.dirname, "..");
const origem = resolve(raiz, "dist", "main.js");
const destino = resolve(raiz, "..", "public", "checkout-validator.js");

await mkdir(resolve(raiz, "..", "public"), { recursive: true });
await copyFile(origem, destino);
console.log(`Publicado: ${destino}`);
