export type SceneShape = {kind:string;layer:string;points?:number[][];center?:number[];radius?:number;color:string;width?:number;alpha:number};
export type ArtworkScene = {width:number;height:number;background:string;shapes:SceneShape[]};
export type HistoricalDemoData = {
  schema:string;sunday:string;captured_at:number;interval:{start:number;end:number;end_ns:string};
  artwork:{title:string;description:string;composition:string;ai_provider:string;image_hash:string;seed:string;merkle_root:string};
  statistics:{total_swaps:number;unique_chains:number;particle_count:number;chains?:Record<string,number>;
    dominant_routes?:Record<string,number>;activity?:number[];public_volume_usd?:string;volume_coverage?:number};
  checkpoint:{height:number;hash:string;timestamp_ns:string};beacon:{round:number;released_at:number;randomness:string};
  snapshot_sha256:string;provenance_sha256:string;
  verification:{checks:Record<string,boolean>;scope:string;rerendered_before_publication:boolean};
  files:Record<string,{url:string;sha256:string}>;
};
