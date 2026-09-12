# Phase 3 preflight — run BEFORE any terraform apply with enable_compute=true.
# Usage (PowerShell, from repo root):
#   .\scripts\aws_preflight.ps1
#   .\scripts\aws_preflight.ps1 -AllowNetwork
#   .\scripts\aws_preflight.ps1 -AllowCompute   # also requires -AllowNetwork

param(
    [switch]$AllowNetwork,
    [switch]$AllowCompute
)

$ErrorActionPreference = "Stop"

function Fail($msg) {
    Write-Host "PREFLIGHT FAIL: $msg" -ForegroundColor Red
    exit 1
}

function Ok($msg) {
    Write-Host "OK: $msg" -ForegroundColor Green
}

Write-Host "=== llm-serving-bench AWS preflight ===" -ForegroundColor Cyan
Write-Host "Hard ceiling: `$25 | Alarm: `$15 | Spot only | No NAT | Destroy every session"

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Fail "AWS CLI not found. Install and configure credentials first."
}

try {
    $ident = aws sts get-caller-identity --output json | ConvertFrom-Json
    Ok "AWS identity $($ident.Arn)"
} catch {
    Fail "aws sts get-caller-identity failed. Configure credentials."
}

$budgets = aws budgets describe-budgets --account-id $ident.Account --output json 2>$null | ConvertFrom-Json
$names = @()
if ($budgets -and $budgets.Budgets) {
    $names = $budgets.Budgets | ForEach-Object { $_.BudgetName }
}
if (-not ($names | Where-Object { $_ -match "llm-serving-bench" })) {
    Write-Host "WARN: No llm-serving-bench budget found yet. First apply should create it (enables=false)." -ForegroundColor Yellow
} else {
    Ok "Found budget(s): $($names -join ', ')"
}

# Refuse dangerous tfvars if present
$tfvars = Join-Path $PSScriptRoot "..\terraform\terraform.tfvars"
if (Test-Path $tfvars) {
    $raw = Get-Content $tfvars -Raw
    if ($raw -match 'use_spot\s*=\s*false') {
        Fail "terraform.tfvars sets use_spot=false (on-demand forbidden)."
    }
    if ($raw -match 'asg_max_size\s*=\s*[2-9]') {
        Fail "terraform.tfvars asg_max_size > 1 forbidden under `$25 ceiling."
    }
    if ($raw -match 'enable_compute\s*=\s*true' -and -not $AllowCompute) {
        Fail "enable_compute=true but you did not pass -AllowCompute. Refusing."
    }
    if ($raw -match 'enable_network\s*=\s*true' -and -not $AllowNetwork -and -not $AllowCompute) {
        Fail "enable_network=true but you did not pass -AllowNetwork. Refusing."
    }
    if ($raw -match 'enable_compute\s*=\s*true' -and $raw -notmatch 'enable_network\s*=\s*true') {
        Fail "enable_compute requires enable_network=true."
    }
    Ok "terraform.tfvars basic safety checks passed"
} else {
    Write-Host "WARN: no terraform.tfvars yet - copy terraform.tfvars.example" -ForegroundColor Yellow
}

if ($AllowCompute) {
    Write-Host ""
    Write-Host "COMPUTE UNLOCK ACKNOWLEDGEMENT" -ForegroundColor Yellow
    Write-Host "You are about to allow resources that cost money (spot GPU + ALB)."
    Write-Host "Type exactly: DESTROY AFTER SESSION"
    $ack = Read-Host "Acknowledgement"
    if ($ack -ne "DESTROY AFTER SESSION") {
        Fail "Acknowledgement mismatch. Compute unlock aborted."
    }
    Ok "Compute unlock acknowledged"
}

Write-Host ""
Ok "Preflight passed. Next:"
Write-Host "  cd terraform"
Write-Host "  terraform init"
Write-Host "  terraform plan"
Write-Host "  # first apply: enable_network=false enable_compute=false  (budget only)"
Write-Host "  terraform apply"
Write-Host "  Confirm SNS email from AWS, then proceed carefully."
