"use client";
import {useEffect,useState} from "react";
export function FrozenArtwork({url,sha256,title}:{url:string;sha256:string;title:string}){
 const [image,setImage]=useState(""),[error,setError]=useState("");
 useEffect(()=>{const abort=new AbortController();let objectURL="";setImage("");setError("");
  void(async()=>{try{const response=await fetch(url,{signal:abort.signal});if(!response.ok)throw new Error("Artwork unavailable");
   const bytes=await response.arrayBuffer();const digest=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");
   if(digest!==sha256)throw new Error("Artwork integrity check failed");
   if(!abort.signal.aborted){objectURL=URL.createObjectURL(new Blob([bytes],{type:"image/svg+xml"}));setImage(objectURL);}
  }catch(e){if(!abort.signal.aborted)setError((e as Error).message);}})();
  return()=>{abort.abort();if(objectURL)URL.revokeObjectURL(objectURL);};
 },[url,sha256]);
 return error?<p role="alert">{error}</p>:image?<img src={image} alt={title}/>:<p role="status">Reading the artwork from NEAR…</p>;
}
