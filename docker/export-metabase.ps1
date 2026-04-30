param(
    [string]$OutputDir = "metabase-transfer"
)

$ErrorActionPreference = "Stop"

function Get-DotEnvValue {
    param(
        [string]$Name,
        [string]$Default
    )

    if (-not (Test-Path ".env")) {
        return $Default
    }

    $line = Get-Content ".env" | Where-Object { $_ -match "^\s*$Name\s*=" } | Select-Object -First 1
    if (-not $line) {
        return $Default
    }

    return (($line -split "=", 2)[1]).Trim().Trim('"').Trim("'")
}

$dbUser = Get-DotEnvValue -Name "DB_USER" -Default "postgres"
$metabaseDbName = Get-DotEnvValue -Name "METABASE_DB_NAME" -Default "metabase"

New-Item -ItemType Directory -Force $OutputDir | Out-Null

Write-Host "Starting PostgreSQL and preparing the Metabase application database..."
docker compose up -d db
docker compose run --rm metabase-db-init

Write-Host "Exporting Metabase PostgreSQL database: $metabaseDbName"
docker compose exec -T db pg_dump -U $dbUser -d $metabaseDbName -Fc -f /tmp/metabase.dump
docker compose cp db:/tmp/metabase.dump (Join-Path $OutputDir "metabase.dump")

$manifestPath = Join-Path $OutputDir "README.txt"
@"
Metabase transfer package

This folder contains metabase.dump, a PostgreSQL dump of the Metabase
application database. It contains Metabase users, cards, dashboards,
collections, database connection settings and embed settings.

Copy this whole folder to the new computer, then run:

  .\docker\import-metabase.ps1
"@ | Set-Content -Path $manifestPath -Encoding UTF8

Write-Host ""
Write-Host "Done. Copy this folder to the new computer:"
Write-Host "  $OutputDir"
