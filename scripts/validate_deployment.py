"""Validate Render against its official schema; inspect local artifact isolation rules."""
import argparse
import json
from pathlib import Path
import httpx
import yaml
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[1]
SCHEMA_URL="https://render.com/schema/render.yaml.json"

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--refresh-schema",action="store_true");args=parser.parse_args()
    schema_path=ROOT/"deploy/schemas/render.schema.json"
    if args.refresh_schema:
        response=httpx.get(SCHEMA_URL,timeout=30);response.raise_for_status()
        schema_path.parent.mkdir(parents=True,exist_ok=True)
        schema_path.write_text(json.dumps(response.json(),indent=2)+"\n",encoding="utf-8")
    schema=json.loads(schema_path.read_text(encoding="utf-8"))
    value=yaml.safe_load((ROOT/"render.yaml").read_text(encoding="utf-8"))
    errors=sorted(Draft202012Validator(schema).iter_errors(value),key=lambda e:str(e.path))
    if errors:
        for error in errors:print(f"Render {list(error.path)}: {error.message}")
        raise SystemExit(1)
    assert len(value["services"])==1
    service=value["services"][0]
    assert service["type"]=="web" and service["numInstances"]==1
    assert service["disk"]["mountPath"]=="/app/data"
    env={item["key"]:item for item in service["envVars"]}
    assert env["SERVICE_ROLE"]["value"]=="combined"
    assert env["NEAR_NETWORK"]["value"]=="testnet"
    assert env["ENABLE_CHAIN_WRITES"]["value"]=="false"
    assert not any(key.startswith("S3_") or key=="ARTIFACT_PUBLIC_URL" for key in env)
    assert service["autoDeployTrigger"]=="off"
    frontend=json.loads((ROOT/"frontend/vercel.json").read_text())
    assert frontend["framework"]=="nextjs"
    print("Render schema and single testnet service/disk boundaries pass; Vercel Next.js config passes.")

if __name__=="__main__":main()
