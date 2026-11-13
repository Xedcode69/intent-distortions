export type Trait={trait_type:string;value:string|number};
export type TraitBundle={schema:string;name:string;description:string;attributes:Trait[];edition_attributes?:Trait[];sha256:string;
 source:{provenance_sha256:string;manifest_sha256:string;image_sha256:string;seed:string;merkle_root:string};onchain_status?:string;mint_status?:string};
function stable(value:unknown):unknown{
 if(Array.isArray(value))return value.map(stable);
 if(value!==null&&typeof value==="object")return Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b,"en")).map(([key,v])=>[key,stable(v)]));
 return value;
}
export async function verifyTraitDocument(bundle:TraitBundle,bytes:ArrayBuffer):Promise<boolean>{
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");
 if(hash!==bundle.sha256)return false;
 try{
  const document=JSON.parse(new TextDecoder().decode(bytes));
  const expected={schema:bundle.schema,name:bundle.name,description:bundle.description,attributes:bundle.attributes,source:bundle.source};
  return JSON.stringify(stable(document))===JSON.stringify(stable(expected));
 }catch{return false;}
}
