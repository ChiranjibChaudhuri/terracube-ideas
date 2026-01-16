import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const fileDir = path.dirname(fileURLToPath(import.meta.url));
const dggalModulePath = path.resolve(fileDir, '../lib/dggal/dggal.js');
export const loadDggal = async () => {
    const mod = await import(pathToFileURL(dggalModulePath).href);
    const DGGALClass = mod.DGGAL ?? mod.default;
    return DGGALClass.init();
};
