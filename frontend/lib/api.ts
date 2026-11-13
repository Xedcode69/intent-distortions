import { useQuery } from "@tanstack/react-query";
export type Art = {
  id:string; edition:string; number:number; mode:string; title:string; description:string;
  composition:string; palette:string[]; image:string; svg:string; thumbnail:string; image_hash:string;
  seed:string; merkle_root:string; start:number; end:number; ai_provider:string;
  provenance:{uri:string;sha256:string}; manifest:{uri:string;sha256:string};
  stats:{total_swaps:number;unique_chains:number;chain_diversity_score:number;chains:Record<string,number>;activity:number[];public_volume_usd:string;volume_coverage:number;particle_count:number;dominant_routes:Record<string,number>};
  block:{height:number;hash:string;verified:boolean}; nft:{status:string;token_id:string|null}; auction:{status:string;highest_bid:string|null};
};
export type Health = { mode:string;network:"testnet"|"mainnet";integrations:Record<string,string>;contracts:{nft:string;auction:string}};
export async function api<T>(path:string, init?:RequestInit):Promise<T> {
  const response=await fetch(`/api/v1${path}`,init);
  if(!response.ok) {const body=await response.json().catch(()=>({}));const error=new Error(body.detail||`Request failed (${response.status})`) as Error & {status:number};error.status=response.status;throw error;}
  return response.json();
}
export function useAPI<T>(path:string) { return useQuery<T>({queryKey:[path],queryFn:()=>api<T>(path),refetchInterval:path.includes("marketplace")||path.includes("auctions")||path.includes("economy")||path.includes("epochs/current")||path==="/health"?15000:false}); }
export function short(value:string, length=8) {return value.length>length*2?`${value.slice(0,length)}…${value.slice(-length)}`:value;}
export function date(time:number) { return new Date(time*1000).toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric",timeZone:"UTC"}); }
export function yocto(value:string) {const n=BigInt(value);return `${n/10n**24n}.${(n%10n**24n).toString().padStart(24,"0").slice(0,4)}`;}
export function toYocto(value:string) {
  if(!/^\d+(\.\d{1,24})?$/.test(value)) throw new Error("Enter a positive NEAR amount with up to 24 decimals");
  const [a,b=""]=value.split("."); return (BigInt(a)*10n**24n+BigInt(b.padEnd(24,"0"))).toString();
}
