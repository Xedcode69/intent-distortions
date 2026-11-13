export const ART_FAMILIES=["orbital_network","fractal_branches","crystalline","flow_field","spiral_constellation","particle_nebula"] as const;
export type FamilyProof={policy:string;family:string;index:number;counter:number;digest:string};

export async function verifyFamilySelection(seed:string,family:string,proof:FamilyProof){
  if(!/^[a-f0-9]{64}$/.test(seed)||proof.policy!=="seed-rejection-six-v1"||!Number.isInteger(proof.counter)||proof.counter<0||proof.counter>1024)return false;
  const key=await crypto.subtle.importKey("raw",new Uint8Array(seed.match(/../g)!.map(byte=>parseInt(byte,16))),{name:"HMAC",hash:"SHA-256"},false,["sign"]);
  const label=new TextEncoder().encode("NEAR_ECHOES_FAMILY_V1"),limit=(1n<<256n)-((1n<<256n)%6n);
  for(let counter=0;counter<=proof.counter;counter++){
    const message=new Uint8Array(label.length+8);message.set(label);new DataView(message.buffer).setBigUint64(label.length,BigInt(counter),false);
    const digest=Array.from(new Uint8Array(await crypto.subtle.sign("HMAC",key,message)),byte=>byte.toString(16).padStart(2,"0")).join("");
    const value=BigInt("0x"+digest);
    if(value<limit){const index=Number(value%6n);return counter===proof.counter&&proof.digest===digest&&proof.index===index&&proof.family===ART_FAMILIES[index]&&family===ART_FAMILIES[index];}
  }
  return false;
}
