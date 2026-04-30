param(
    [string]$InputDir = "metabase-transfer"
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
$dumpPath = Join-Path $InputDir "metabase.dump"
$sourceDb = Join-Path $InputDir "metabase.db.mv.db"
if (-not (Test-Path $sourceDb)) {
    $sourceDb = Join-Path $InputDir "metabase.db/metabase.db.mv.db"
}

if (-not (Test-Path $dumpPath) -and -not (Test-Path $sourceDb)) {
    throw "Metabase transfer was not found. Expected '$dumpPath' or '$sourceDb'."
}

$sourceTrace = Join-Path $InputDir "metabase.db.trace.db"
if (-not (Test-Path $sourceTrace)) {
    $sourceTrace = Join-Path $InputDir "metabase.db/metabase.db.trace.db"
}

$rootDb = Join-Path $InputDir "metabase.db.mv.db"
if ((Resolve-Path $sourceDb).Path -ne (Resolve-Path $rootDb -ErrorAction SilentlyContinue).Path) {
    Copy-Item -LiteralPath $sourceDb -Destination $rootDb -Force
}

if (Test-Path $sourceTrace -and -not (Test-Path (Join-Path $InputDir "metabase.db.trace.db"))) {
    Copy-Item -LiteralPath $sourceTrace -Destination (Join-Path $InputDir "metabase.db.trace.db") -Force
}

Write-Host "Stopping compose Metabase service if it exists..."
docker compose stop metabase *> $null

Write-Host "Starting PostgreSQL..."
docker compose up -d db

Write-Host "Resetting Metabase PostgreSQL database: $metabaseDbName"
docker compose exec -T db dropdb -U $dbUser --if-exists $metabaseDbName
docker compose exec -T db createdb -U $dbUser $metabaseDbName

if (Test-Path $dumpPath) {
    Write-Host "Restoring Metabase PostgreSQL dump..."
    docker compose cp $dumpPath db:/tmp/metabase.dump
    docker compose exec -T db pg_restore -U $dbUser -d $metabaseDbName /tmp/metabase.dump
} else {
    Write-Host "Migrating H2 Metabase data into Docker PostgreSQL..."

    $inputPath = (Resolve-Path $InputDir).Path

    docker compose run --rm --no-deps --entrypoint java -v "${inputPath}:/metabase-transfer" metabase --add-opens java.base/java.nio=ALL-UNNAMED -jar /app/metabase.jar load-from-h2 /metabase-transfer/metabase.db
}

Write-Host "Starting Metabase with PostgreSQL application database..."
docker compose up -d metabase

Write-Host ""
Write-Host "Done. Open Metabase:"
Write-Host "  http://localhost:3000"
Write-Host ""
Write-Host "If dashboards open but charts are empty, update the database connection in Metabase:"
Write-Host "  Admin settings -> Databases -> ButterCafe -> Host: db, Port: 5432"
