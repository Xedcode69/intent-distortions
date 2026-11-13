import { mkdir,copyFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
const root=fileURLToPath(new URL("../",import.meta.url));
const output=resolve(root,"dist/demo");
await mkdir(resolve(output,"assets"),{recursive:true});
for(const name of ["index.html","styles.css","app.mjs","core.mjs","assets/artwork.png","assets/artwork.svg","assets/thumbnail.webp","assets/scene.json","assets/example.json"]){
  await copyFile(resolve(root,"demo",name),resolve(output,name));
}
console.log("Packaged standalone educational demo (9 public files, synthetic data only).");
