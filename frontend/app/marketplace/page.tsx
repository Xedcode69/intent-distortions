import {Marketplace} from "@/components/marketplace";
export default async function Page({searchParams}:{searchParams:Promise<{token?:string|string[]}>}){
 const {token}=await searchParams;
 const initialToken=typeof token==="string"&&/^[a-zA-Z0-9_.-]{1,64}$/.test(token)?token:"";
 return <Marketplace initialToken={initialToken}/>;
}
