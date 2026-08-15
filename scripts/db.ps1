# db.ps1 - "Excel ikona" pro MCP-Jobs databazi.
# Otevre PostgreSQL konzoli (psql) jedinym prikazem, jako spustis Excel.
#
# Pouziti:
#   pwsh scripts\db.ps1            - otevrit interaktivni psql konzoli
#   pwsh scripts\db.ps1 tables     - vypsat tabulky + pocet radku
#   pwsh scripts\db.ps1 query "SQL" - spustit jeden dotaz a skoncit
#   pwsh scripts\db.ps1 status     - stav DB kontejneru
#
# Priklady:
#   pwsh scripts\db.ps1 query "SELECT * FROM ads LIMIT 5;"
#   pwsh scripts\db.ps1 query "SELECT status, COUNT(*) FROM ads GROUP BY status;"

$ErrorActionPreference = "Stop"

$container = "mcp-jobs-postgres"
$user = "mcpjobs"
$db = "mcpjobs"

function Test-DbRunning {
    $status = docker inspect $container --format "{{.State.Status}}" 2>$null
    if ($status -ne "running") {
        Write-Error "DB kontejner nebezi. Spust ho: docker compose up -d"
    }
}

$cmd = $args[0]

switch ($cmd) {
    "status" {
        docker compose ps --format "table {{.Name}}\t{{.Status}}"
    }
    "tables" {
        Test-DbRunning
        docker exec $container psql -U $user -d $db -c "\dt" -c "SELECT 'ads' AS table_name, COUNT(*) AS rows FROM ads UNION ALL SELECT 'pipeline_runs', COUNT(*) FROM pipeline_runs;"
    }
    "query" {
        Test-DbRunning
        $sql = $args[1]
        if (-not $sql) {
            Write-Error "Zadej SQL dotaz: pwsh scripts\db.ps1 query ""SELECT * FROM ads LIMIT 5;"""
        }
        docker exec $container psql -U $user -d $db -P pager=off -c $sql
    }
    default {
        Test-DbRunning
        Write-Output "=== MCP-Jobs PostgreSQL konzole (psql) ==="
        Write-Output "Databaze: $db | Uzivatel: $user | Port: 5432"
        Write-Output "Konec: \q"
        Write-Output ""
        docker exec -it $container psql -U $user -d $db -P pager=off
    }
}