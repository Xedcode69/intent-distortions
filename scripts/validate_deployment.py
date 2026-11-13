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
    services={service["name"]:service for service in value["services"]}
    assert services["near-echoes-api"]["type"]=="pserv"
    assert services["near-echoes-worker"]["numInstances"]==1
    assert services["near-echoes-explainer"]["runtime"]=="static"
    assert "envVars" not in services["near-echoes-explainer"]
    for service in services.values():assert service["autoDeployTrigger"]=="off"
    template=json.loads((ROOT/"deploy/artifacts.cloudformation.json").read_text())
    assert template["Resources"]["Artifacts"]["DeletionPolicy"]=="Retain"
    assert template["Resources"]["Artifacts"]["Properties"]["ObjectLockEnabled"] is True
    print("Render Blueprint matches official schema; production/demo isolation checks pass.")
    print("S3 CloudFormation JSON parses and retention checks pass; AWS-side resource validation still required.")

if __name__=="__main__":main()
