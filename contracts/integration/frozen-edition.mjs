// Contract integration fixture: deliberately tiny synthetic geometry, no live AI.
import {createHash} from "node:crypto";
import {readFile} from "node:fs/promises";
const sha=b=>createHash("sha256").update(b).digest("hex");
export async function mintFrozen(operator,nft,release,epoch,opts){
 const fixture=JSON.parse(await readFile(new URL("./frozen-fixture.json",import.meta.url),"utf8"));
 const recipe=Buffer.from(fixture.recipe_base64,"base64"),title="Contract fixture",token=`ECHO-${String(epoch).padStart(6,"0")}`;
 const still=Buffer.from(fixture.static),motion=Buffer.from(fixture.animated);
 if(sha(recipe)!==fixture.recipe_sha256||sha(still)!==fixture.static_sha256||sha(motion)!==fixture.animated_sha256)throw new Error("Altered contract fixture");
 const seed="01".repeat(32),merkle="02".repeat(32);
 const proof=Buffer.from(JSON.stringify({seed,merkle_root:merkle,recipe_sha256:sha(recipe),direction:{composition:"crystalline"},ai:{provider:"near_ai_cloud",policy:"first-valid-v1",model:"synthetic-contract-fixture"}}));
 const metadata={title,media:`near://${nft.accountId}/${token}/static.svg`,media_hash:Buffer.from(sha(still),"hex").toString("base64"),copies:1,
  reference:"data:application/json;base64,"+proof.toString("base64"),reference_hash:Buffer.from(sha(proof),"hex").toString("base64"),
  extra:JSON.stringify({format:"intent-distortions-weekly-onchain-v1",attributes:[{trait_type:"Material",value:"glass"}],traits_reference:{sha256:"03".repeat(32)}})};
 await operator.call(nft,"begin_onchain_art",{release_ns:String(release),metadata,commitment:{epoch,image_hash:sha(still),provenance_hash:sha(proof),merkle_root:merkle,seed,block_hash:"sandbox-block"},recipe_sha256:sha(recipe),recipe_bytes:recipe.length,static_sha256:sha(still),animated_sha256:sha(motion)},opts(10n**24n));
 await operator.call(nft,"append_onchain_recipe",{token_id:token,offset:0,data:recipe.toString("base64")},opts());
 for(const animated of [false,true])await operator.call(nft,"verify_onchain_view",{token_id:token,animated},opts());
 await operator.call(nft,"mint_onchain_art",{token_id:token},opts(10n**24n));
 const state=await nft.view("get_onchain_art",{token_id:token});
 if(!state.sealed||state.static_sha256!==sha(still)||state.animated_sha256!==sha(motion))throw new Error("Frozen views differ");
 return token;
}
