const encoder=new TextEncoder();
export const hex=bytes=>[...bytes].map(x=>x.toString(16).padStart(2,"0")).join("");
export const unhex=value=>Uint8Array.from(value.match(/../g).map(x=>parseInt(x,16)));
export const concat=(...arrays)=>{const out=new Uint8Array(arrays.reduce((n,a)=>n+a.length,0));let offset=0;for(const a of arrays){out.set(a,offset);offset+=a.length;}return out;};
export const utf8=value=>encoder.encode(value);
export const sha=async bytes=>new Uint8Array(await crypto.subtle.digest("SHA-256",bytes));
export function canonical(value){if(Array.isArray(value))return `[${value.map(canonical).join(",")}]`;if(value!==null&&typeof value==="object")return `{${Object.keys(value).sort().map(k=>`${JSON.stringify(k)}:${canonical(value[k])}`).join(",")}}`;return JSON.stringify(value);}
export function u64(value){const out=new Uint8Array(8);new DataView(out.buffer).setBigUint64(0,BigInt(value),false);return out;}
export function base58decode(value){const alphabet="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";let n=0n;for(const char of value){const i=alphabet.indexOf(char);if(i<0)throw new Error("Invalid base58");n=n*58n+BigInt(i);}const bytes=[];while(n){bytes.unshift(Number(n%256n));n/=256n;}for(const char of value){if(char!=="1")break;bytes.unshift(0);}return Uint8Array.from(bytes);}
export async function merkleRoot(records){let row=await Promise.all(records.map(async r=>sha(concat(new Uint8Array([0]),await sha(concat(utf8("ECHO_RECORD_V1"),utf8(canonical(r))))))));if(!row.length)return hex(await sha(utf8("ECHO_EMPTY_V1")));while(row.length>1){const next=[];for(let i=0;i<row.length;i+=2)next.push(await sha(concat(new Uint8Array([1]),row[i],row[Math.min(i+1,row.length-1)])));row=next;}return hex(row[0]);}
export async function deriveSeed(example,root){return hex(await sha(concat(utf8("NEAR_ECHOES_ART_V1"),u64(example.epoch),unhex(root),base58decode(example.block.hash),unhex(example.randomness),unhex(example.previous_image_hash))));}
export async function selectTimestamp(epoch,randomness,start){const seed=await sha(concat(utf8("NEAR_ECHOES_BLOCK_SELECTION_V1"),u64(epoch),unhex(randomness)));const duration=61200n,limit=(1n<<256n)-((1n<<256n)%duration);let n=BigInt(`0x${hex(seed)}`),counter=0;while(n>=limit){counter++;n=BigInt(`0x${hex(await sha(concat(utf8("NEAR_ECHOES_REJECT_V1"),seed,u64(counter))))}`);}return start+Number(n%duration);}
