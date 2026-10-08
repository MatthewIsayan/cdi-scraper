Set-Location -LiteralPath $PSScriptRoot
node --experimental-sqlite --disable-warning=ExperimentalWarning --import tsx ../src/scrape.ts
