param([string]$CaFile = "")
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskContracts = Join-Path $taskRoot 'contracts'
foreach ($taskName in @('echo_nft.wasm','echo_auction.wasm','echo_vault.wasm','echo_market.wasm')) {
    if (-not (Test-Path -LiteralPath (Join-Path $taskContracts "target/wasm32-unknown-unknown/release/$taskName"))) {
        throw 'Build current contracts first: uv run --locked python scripts/build_contracts.py --test'
    }
}
$taskDockerArgs = @('run','--rm',
    '--mount',"type=bind,source=$taskContracts/integration,target=/source,readonly",
    '--mount',"type=bind,source=$taskContracts/target/wasm32-unknown-unknown/release,target=/work/contracts/target/wasm32-unknown-unknown/release,readonly",
    '--mount',"type=bind,source=$taskRoot/fixtures,target=/work/fixtures,readonly",
    '-e','SANDBOX_ARTIFACT_URL=https://s3-us-west-1.amazonaws.com/build.nearprotocol.com/nearcore/Linux-x86_64/2.14.0/near-sandbox.tar.gz')
if ($CaFile) {
    $taskCaPath=(Resolve-Path -LiteralPath $CaFile).Path
    $taskDockerArgs+=@('--mount',"type=bind,source=$taskCaPath,target=/certs/extra-ca.pem,readonly",'-e','NODE_EXTRA_CA_CERTS=/certs/extra-ca.pem')
}
$taskDockerArgs+=@('node:22-trixie-slim','sh','-lc',
    'mkdir -p /work/contracts/integration && cp /source/package.json /source/package-lock.json /source/lifecycle.test.mjs /work/contracts/integration/ && cd /work/contracts/integration && npm ci --ignore-scripts --no-audit --no-fund && npm test')
& docker @taskDockerArgs
if ($LASTEXITCODE -ne 0) { throw 'NEAR sandbox lifecycle failed; inspect the test output.' }
