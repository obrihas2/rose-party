[CmdletBinding()]
param(
	[string]$RelayUrl
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RelayWorker = Join-Path $Root "relay-worker"
$RelayConfig = Join-Path $Root "party\network\relay_config.py"

function Require-Command([string]$Name, [string]$InstallHint) {
	if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
		throw "$Name was not found. $InstallHint"
	}
}

Require-Command "node" "Install Node.js LTS from https://nodejs.org/ and run this script again."
Require-Command "npm" "Install Node.js LTS from https://nodejs.org/ and run this script again."

if (-not (Test-Path (Join-Path $RelayWorker "wrangler.toml"))) {
	throw "relay-worker/wrangler.toml was not found. Run this script from the Rose repository."
}

Push-Location $RelayWorker
try {
	Write-Host "Installing relay dependencies..." -ForegroundColor Cyan
	npm install

	Write-Host "Opening Cloudflare login... approve the browser request, then return here." -ForegroundColor Cyan
	npx wrangler login

	Write-Host "Deploying the Rose Party relay..." -ForegroundColor Cyan
	$deployOutput = (& npx wrangler deploy 2>&1 | Tee-Object -Variable deployLines | Out-String)
	if ($LASTEXITCODE -ne 0) {
		throw "Cloudflare deployment failed. Review the Wrangler output above."
	}

	if (-not $RelayUrl) {
		$urlMatch = [regex]::Match($deployOutput, 'https://[a-zA-Z0-9.-]+\.workers\.dev')
		if ($urlMatch.Success) {
			$RelayUrl = $urlMatch.Value
		}
	}
} finally {
	Pop-Location
}

if (-not $RelayUrl) {
	$RelayUrl = Read-Host "Wrangler did not print the URL. Paste the deployed HTTPS Worker URL"
}

$RelayUrl = $RelayUrl.Trim().TrimEnd('/')
if ($RelayUrl -notmatch '^https://') {
	throw "Relay URL must start with https://, for example https://rose-party-relay.example.workers.dev"
}

$HealthUrl = "$RelayUrl/"
Write-Host "Checking relay health at $HealthUrl ..." -ForegroundColor Cyan
$health = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 20
if ($health.status -ne "ok") {
	throw "Relay health check did not return status=ok."
}

$WssUrl = $RelayUrl -replace '^https://', 'wss://'
$configDirectory = Split-Path -Parent $RelayConfig
New-Item -ItemType Directory -Force -Path $configDirectory | Out-Null
Set-Content -Path $RelayConfig -Value "RELAY_URL = `"$WssUrl`"`r`n" -Encoding utf8

Write-Host "Relay is ready: $WssUrl" -ForegroundColor Green
Write-Host "Relay config written to: $RelayConfig" -ForegroundColor Green
Write-Host "The config is tracked by Git — commit it so every build uses this relay." -ForegroundColor DarkGray
Write-Host "Next step: run python scripts/build_pyinstaller.py from the Rose repository root." -ForegroundColor Cyan
